"""Synthetic actual returns, unchanged purchase originals and shared stock replay."""
import base64
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import business_schema
from core import Office,Problem
from business_purchase_changes import PurchaseChanges,validate_integrity,protected_tables,mixed_stock_events,dispatch
from business_inventory import BusinessInventory
from business_inventory_counts import InventoryCounts
from business_organization import Organization
import test_business_purchasing as purchasing_fixture


class PurchaseChangesTests(unittest.TestCase):
    setUp_base=purchasing_fixture.PurchasingTests.setUp
    req=purchasing_fixture.PurchasingTests.req
    actor=purchasing_fixture.PurchasingTests.actor
    make_order=purchasing_fixture.PurchasingTests.make_order
    grant=purchasing_fixture.PurchasingTests.grant
    confirmation=purchasing_fixture.PurchasingTests.confirmation
    receipt=purchasing_fixture.PurchasingTests.receipt
    receive=purchasing_fixture.PurchasingTests.receive
    def setUp(self):
        self.setUp_base();self.changes=PurchaseChanges(self.office,clock=self.clock)
        self.order=self.make_order(items=[dict(article_id=self.article['id'],quantity='10')])
        self.confirm_body=self.confirmation();self.confirmed=self.api.confirm(self.owner,self.order['id'],self.confirm_body)
        self.evidence=self.upload()
    def error(self,status,fn,*args,**kwargs):
        with self.assertRaises(Problem) as caught:fn(*args,**kwargs)
        self.assertEqual(caught.exception.status,status,caught.exception.message);return caught.exception
    def upload(self,filename='actual-change.pdf'):
        raw=b'%PDF-1.7\nSynthetic actual supplier original\n%%EOF'
        return self.changes.upload(self.owner,self.order['id'],self.req(filename=filename,media_type='application/pdf',content_base64=base64.b64encode(raw).decode()))
    def detail(self):return self.changes.detail(self.owner,self.order['id'])
    def basis(self):
        current=self.detail();return dict(source_revision=current['source_revision'],expected_receipt_revision=current['receipt_revision'],expected_amendment_revision=current['amendment_revision'],expected_return_revision=current['return_revision'],source_sha256=current['source_sha256'])
    def amendment(self,amount,**changes):
        value=dict(**self.basis(),kind='quantity_change',reference='SYN-AMEND-'+self.req()['request_id'][:8],effective_on='2026-11-02',reason='Actual externally agreed quantities',evidence_id=self.evidence['id'],lines=[dict(line_index=0,authorized_quantity=amount)]);value.update(changes);return value
    def returning(self,receipt,amount,**changes):
        value=dict(**self.basis(),reference='SYN-RETURN-'+self.req()['request_id'][:8],returned_on='2026-11-02',reason='Actual physical supplier return',evidence_id=self.evidence['id'],lines=[dict(receipt_id=receipt['id'],line_index=0,quantity=amount)]);value.update(changes);return value
    def prepare(self,action,data,actor=None):
        preview=self.changes.preview(actor or self.owner,self.order['id'],action,data)
        return self.req(**data,preview_sha256=preview['preview_sha256'],confirmation=True)
    def apply(self,action,data,actor=None):
        body=self.prepare(action,data,actor);result=self.changes.confirm(actor or self.owner,self.order['id'],action,body);return result,body
    def balance(self):return self.inventory.balance(self.owner,self.location['id'],self.article['id'])
    def count(self,amount):
        api=InventoryCounts(self.office,clock=self.clock)
        opened=api.command(self.owner,'open',self.req(location_id=self.location['id'],article_ids=[self.article['id']],title='Synthetic actual count',counted_on='2026-11-02',correction_of=None,reason='Actual units counted'))
        counted=api.command(self.owner,'count',self.req(revision=opened['revision'],lines=[dict(article_id=self.article['id'],quantity=amount,reason='Actual difference verified')]),opened['id'])
        return api.command(self.owner,'approve',self.req(revision=counted['revision'],confirmed=True,zero_stock_unit_costs={}),counted['id'])
    def valid(self):self.assertTrue(business_schema.validate_integrity(self.office))

    def test_partial_receipt_return_reservations_originals_and_exact_replay(self):
        receipt_body=self.receipt(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')]);received=self.api.receive(self.owner,self.order['id'],receipt_body)
        original=tuple(self.office.db.execute('SELECT * FROM business_purchase_orders WHERE id=?',(self.order['id'],)).fetchone())
        self.inventory.reserve(self.owner,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='2'))
        self.error(409,self.changes.preview,self.owner,self.order['id'],'supplier-returns',self.returning(received,'5'))
        result,body=self.apply('supplier-returns',self.returning(received,'2'))
        self.assertEqual((self.balance()['on_hand'],self.balance()['available']),('4.0000','2.0000'))
        item=self.detail()['items'][0];self.assertEqual((item['received_quantity'],item['returned_quantity'],item['retained_quantity'],item['remaining_quantity']),('6.0000','2.0000','4.0000','4.0000'))
        self.assertEqual(self.changes.confirm(self.owner,self.order['id'],'supplier-returns',body),result)
        self.assertEqual(self.api.receive(self.owner,self.order['id'],receipt_body),received)
        self.assertEqual(self.api.confirm(self.owner,self.order['id'],self.confirm_body),self.confirmed)
        self.assertEqual(tuple(self.office.db.execute('SELECT * FROM business_purchase_orders WHERE id=?',(self.order['id'],)).fetchone()),original)
        self.assertEqual(self.inventory.cost_report(self.owner,self.project)['material_actual_net'],'0.00');self.valid()

    def test_explicit_replacement_capacity_new_receipt_version_and_original_acceptance(self):
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        self.apply('supplier-returns',self.returning(first,'2'))
        amended,amend_body=self.apply('amendments',self.amendment('12',kind='replacement'))
        self.assertEqual(amended['order']['items'][0]['remaining_quantity'],'6.0000')
        body=self.receipt(expected_receipt_revision=1,receipt_reference='SECOND',lines=[dict(line_index=0,quantity='6',unit_cost_net='3')])
        self.error(409,self.api.receive,self.owner,self.order['id'],body)
        body['expected_amendment_revision']=1;second=self.api.receive(self.owner,self.order['id'],body)
        self.assertEqual(self.api.get(self.owner,self.order['id'])['amendment_revision'],1)
        self.assertEqual((self.detail()['items'][0]['retained_quantity'],self.balance()['on_hand']),('10.0000','10.0000'))
        self.apply('amendments',self.amendment('13'))
        self.assertEqual(self.api.receive(self.owner,self.order['id'],body),second)
        self.assertEqual(self.changes.confirm(self.owner,self.order['id'],'amendments',amend_body),amended)
        self.error(409,self.api.receive,self.owner,self.order['id'],self.receipt(expected_receipt_revision=2,expected_amendment_revision=1,receipt_reference='STALE',lines=[dict(line_index=0,quantity='1',unit_cost_net='3')]))
        self.valid()

    def test_rest_cancellation_retains_actual_received_and_can_only_reopen_explicitly(self):
        self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        self.error(409,self.changes.preview,self.owner,self.order['id'],'amendments',self.amendment('5'))
        changed,_=self.apply('amendments',self.amendment('6',kind='cancel_remaining'))
        self.assertEqual(changed['order']['items'][0]['remaining_quantity'],'0.0000')
        self.assertEqual(self.api.get(self.owner,self.order['id'])['status'],'remainder_cancelled')
        self.error(409,self.api.receive,self.owner,self.order['id'],self.receipt(expected_receipt_revision=1,expected_amendment_revision=1,receipt_reference='OVER',lines=[dict(line_index=0,quantity='1',unit_cost_net='2')]))
        self.assertEqual(self.balance()['on_hand'],'6.0000');self.valid()

    def test_shared_count_return_order_multiple_lines_and_exact_weighted_issue(self):
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        second=self.receive(expected_receipt_revision=1,receipt_reference='SECOND',lines=[dict(line_index=0,quantity='4',unit_cost_net='4')])
        self.count('12')
        data=self.returning(first,'1',lines=[dict(receipt_id=first['id'],line_index=0,quantity='1'),dict(receipt_id=second['id'],line_index=0,quantity='1')])
        result,_=self.apply('supplier-returns',data);self.assertEqual(result['record']['total_book_value_net'],'5.6000')
        self.count('9');self.apply('supplier-returns',self.returning(first,'2'))
        events=[kind for kind,_ in mixed_stock_events(self.office)]
        self.assertEqual(events,['movement','movement','count','supplier_return','supplier_return','count','supplier_return'])
        issue=self.inventory.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='7'))
        self.assertEqual(issue['cost_net'],'19.6000');self.assertEqual(self.inventory._stock(self.location['id'],self.article['id'])[:2],(Decimal(0),Decimal(0)));self.valid()

    def test_return_invalidates_open_count_even_when_quantity_recovers(self):
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')]);counts=InventoryCounts(self.office,clock=self.clock)
        opened=counts.command(self.owner,'open',self.req(location_id=self.location['id'],article_ids=[self.article['id']],title='Original open count',counted_on='2026-11-02',correction_of=None,reason='Original count'))
        self.apply('supplier-returns',self.returning(first,'2'))
        self.inventory.move(self.owner,self.req(kind='receive',article_id=self.article['id'],to_location_id=self.location['id'],quantity='2',unit_cost_net='2'))
        self.assertEqual(self.balance()['on_hand'],'6.0000');self.assertFalse(counts.get(self.owner,opened['id'])['basis_current'])
        self.error(409,counts.command,self.owner,'count',self.req(revision=1,lines=[dict(article_id=self.article['id'],quantity='6',reason='No difference')]),opened['id']);self.valid()

    def test_project_return_cost_corrected_once_and_no_financial_journal_effect(self):
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        issue=self.inventory.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='4'))
        self.error(409,self.changes.preview,self.owner,self.order['id'],'supplier-returns',self.returning(first,'3'))
        self.inventory.move(self.owner,self.req(kind='return',article_id=self.article['id'],to_location_id=self.location['id'],project_id=self.project,quantity='2',reversal_of=issue['id']))
        tables=[r[0] for r in self.office.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'business_accounting_%' OR name LIKE 'business_finance_%' OR name LIKE 'business_bank_%')")]
        before={t:[tuple(r) for r in self.office.db.execute('SELECT * FROM '+t)] for t in tables}
        self.apply('supplier-returns',self.returning(first,'3'))
        self.assertEqual(self.inventory.cost_report(self.owner,self.project)['material_actual_net'],'4.00')
        self.assertEqual({t:[tuple(r) for r in self.office.db.execute('SELECT * FROM '+t)] for t in tables},before);self.valid()

    def test_stale_sources_duplicate_reference_late_failure_and_immutable_history(self):
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')]);data=self.returning(first,'2');body=self.prepare('supplier-returns',data)
        self.inventory.reserve(self.owner,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='1'))
        self.error(409,self.changes.confirm,self.owner,self.order['id'],'supplier-returns',body)
        body=self.prepare('supplier-returns',self.returning(first,'2',reference='ACTUAL-ONE'))
        with patch.object(self.office,'audit',side_effect=RuntimeError('Synthetic failure after stock-out')):
            with self.assertRaises(RuntimeError):self.changes.confirm(self.owner,self.order['id'],'supplier-returns',body)
        self.assertEqual(self.balance()['on_hand'],'6.0000');self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_supplier_return_lines').fetchone()[0],0)
        result=self.changes.confirm(self.owner,self.order['id'],'supplier-returns',body)
        self.error(409,self.changes.preview,self.owner,self.order['id'],'supplier-returns',self.returning(first,'1',reference=' actual-one '))
        self.error(409,self.changes.confirm,self.owner,self.order['id'],'supplier-returns',dict(body,reason='Changed same nonce'))
        for table in protected_tables():
            if self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]:
                with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
                with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('INSERT OR REPLACE INTO '+table+' SELECT * FROM '+table)
        self.assertEqual(self.changes.confirm(self.owner,self.order['id'],'supplier-returns',body),result);self.valid()

    def test_paused_new_actions_original_replay_and_fresh_financial_redaction(self):
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        self.grant(self.tech,'inventory.read','inventory.write','finance.write','finance.read','finance.approve',scope=self.project)
        body=self.prepare('supplier-returns',self.returning(first,'1'),self.tech);result=self.changes.confirm(self.tech,self.order['id'],'supplier-returns',body)
        self.assertIn('book_value_net',result['record']['lines'][0])
        with self.office.db:self.office.db.execute("UPDATE business_permission_grants SET effect='deny',revision=revision+1 WHERE user_id=? AND permission='finance.read'",(self.tech['id'],))
        replay=self.changes.confirm(self.tech,self.order['id'],'supplier-returns',body);self.assertNotIn('book_value_net',replay['record']['lines'][0]);self.assertNotIn('stock_value_net',replay['order']['receipts'][0]['lines'][0]);self.assertNotIn('proof',json.dumps(replay));self.assertFalse(replay['financial_values_visible'])
        self.error(403,self.changes.original,self.tech,self.order['id'],self.evidence['id'])
        organization=Organization(self.office);state=organization.get(self.owner);modules={k:dict(visible=v['visibility_override'],enabled=v['enabled']) for k,v in state['modules'].items()};modules['material']['enabled']=False
        organization.save(self.owner,self.req(revision=state['revision'],needs=state['needs'],modules=modules))
        self.assertEqual(self.changes.confirm(self.tech,self.order['id'],'supplier-returns',body),replay)
        self.error(423,self.apply,'supplier-returns',self.returning(first,'1'))
        self.assertEqual(self.api.confirm(self.owner,self.order['id'],self.confirm_body),self.confirmed)
        with self.office.db:self.office.db.execute('DELETE FROM assignments WHERE user_id=? AND project_id=?',(self.tech['id'],self.project))
        self.error(404,self.changes.confirm,self.tech,self.order['id'],'supplier-returns',body)

    def test_parallel_same_acceptance_and_competing_capacity(self):
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')]);body=self.prepare('supplier-returns',self.returning(first,'4'))
        def run(data):
            office=Office(self.database)
            try:
                try:return PurchaseChanges(office,clock=self.clock).confirm(self.owner,self.order['id'],'supplier-returns',data)
                except Problem as error:return error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[body,body]))
        self.assertEqual(results[0],results[1]);self.assertEqual(self.balance()['on_hand'],'2.0000')
        left=self.prepare('supplier-returns',self.returning(first,'2'));right=self.prepare('supplier-returns',self.returning(first,'2'))
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[left,right]))
        self.assertEqual(sum(isinstance(v,dict) for v in results),1);self.assertIn(409,results);self.assertEqual(self.balance()['on_hand'],'0.0000');self.valid()

    def test_device_origin_and_returns_share_receipt_capacity_in_both_orders(self):
        import test_business_asset_provenance as provenance_fixture
        for return_first in (False,True):
            with self.subTest(return_first=return_first):
                fixture=provenance_fixture.AssetProvenanceTests('runTest');fixture.setUp()
                try:
                    api=PurchaseChanges(fixture.office,clock=fixture.clock)
                    evidence=api.upload(fixture.owner,fixture.order['id'],fixture.req(filename='actual-return.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'%PDF-1.7 actual synthetic return').decode()))
                    def returning():
                        current=api.detail(fixture.owner,fixture.order['id'])
                        return dict(source_revision=current['source_revision'],expected_receipt_revision=current['receipt_revision'],expected_amendment_revision=current['amendment_revision'],expected_return_revision=current['return_revision'],source_sha256=current['source_sha256'],reference='RETURN-ORIGIN',returned_on='2026-11-03',reason='Actual return of unbound unit',evidence_id=evidence['id'],lines=[dict(receipt_id=fixture.receipt['id'],line_index=0,quantity='1')])
                    def post_return():
                        data=returning();preview=api.preview(fixture.owner,fixture.order['id'],'supplier-returns',data)
                        return api.confirm(fixture.owner,fixture.order['id'],'supplier-returns',fixture.req(**data,preview_sha256=preview['preview_sha256'],confirmation=True))
                    if return_first:post_return()
                    origin=fixture.api.create(fixture.owner,fixture.create_body(quantity='2'))
                    if not return_first:post_return()
                    fixture.inv.move(fixture.owner,fixture.req(kind='receive',article_id=fixture.article['id'],to_location_id=fixture.location['id'],quantity='3',unit_cost_net='99'))
                    body=returning();body['reference']='ANOTHER-RETURN'
                    self.error(409,api.preview,fixture.owner,fixture.order['id'],'supplier-returns',body)
                    self.error(409,fixture.inv.move,fixture.owner,fixture.req(kind='return',article_id=fixture.article['id'],to_location_id=fixture.location['id'],project_id=fixture.project,quantity='1',reversal_of=fixture.issue['id']))
                    self.assertEqual(fixture.api.origin(fixture.owner,origin['id'])['quantity'],'2.0000')
                    self.assertTrue(business_schema.validate_integrity(fixture.office))
                finally:fixture.doCleanups()

    def test_forged_stock_valuation_is_rejected_and_original_corruption_blocks_retry(self):
        from business_inventory import validate_integrity as validate_inventory
        from business_purchase_changes import sha
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')]);result,body=self.apply('supplier-returns',self.returning(first,'2'))
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_supplier_return_lines_update_guard')
            row=self.office.db.execute('SELECT * FROM business_supplier_return_lines').fetchone();changed=json.loads(row['payload_json']);changed['book_value_net']='3.0000'
            self.office.db.execute('UPDATE business_supplier_return_lines SET book_value_net=?,payload_json=?,sha256=? WHERE id=?',('3.0000',json.dumps(changed),sha(changed),row['id']))
        with self.assertRaisesRegex(ValueError,'weighted historical'):validate_inventory(self.office)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_purchase_change_evidence_update_guard')
            self.office.db.execute('UPDATE business_purchase_change_evidence SET content=? WHERE id=?',(b'%PDF-corrupt',self.evidence['id']))
        self.error(409,self.changes.confirm,self.owner,self.order['id'],'supplier-returns',body)

    def test_company_export_keeps_original_bytes_and_fach_history_excludes_requests(self):
        import io,zipfile
        from company_export_archive import build,verify
        from company_export_archive import structure
        first=self.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')]);self.apply('supplier-returns',self.returning(first,'2'));self.apply('amendments',self.amendment('12',kind='replacement'))
        raw,manifest=build(self.office,instance_id='a'*32,export_id='b'*32,created_at=self.changes.now(),created_by=self.owner['id'],reason='Synthetic return export',inventory=structure(self.office))
        verify(raw,instance_id='a'*32)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            rows=[json.loads(line) for line in archive.read('data/business_purchase_change_evidence.jsonl').splitlines()]
            self.assertEqual(archive.read(rows[0]['content']['$file']),bytes(self.changes.file(self.order['id'],self.evidence['id'])['content']))
            self.assertNotIn('data/business_purchase_change_requests.jsonl',archive.namelist())
            self.assertEqual(len(archive.read('data/business_supplier_returns.jsonl').splitlines()),1)


class PurchaseChangesMigrationTests(unittest.TestCase):
    def test_actual_historical_copy_adds_schema_without_mutating_old_orders_counts_origins_or_pdf(self):
        import tempfile
        import test_business_asset_provenance as provenance_fixture
        previous=tuple(spec for spec in business_schema.registry() if spec.name!='business_purchase_changes')
        fixture=provenance_fixture.AssetProvenanceTests('runTest')
        patcher=patch.object(business_schema,'registry',return_value=previous);patcher.start();self.addCleanup(patcher.stop)
        fixture.setUp()
        try:
            fixture.api.create(fixture.owner,fixture.create_body())
            counts=InventoryCounts(fixture.office,clock=fixture.clock)
            opened=counts.command(fixture.owner,'open',fixture.req(location_id=fixture.location['id'],article_ids=[fixture.article['id']],title='Existing actual count',counted_on='2026-11-03',correction_of=None,reason='Actual old count'))
            counted=counts.command(fixture.owner,'count',fixture.req(revision=1,lines=[dict(article_id=fixture.article['id'],quantity='2',reason='Found another physical unit')]),opened['id'])
            counts.command(fixture.owner,'approve',fixture.req(revision=2,confirmed=True,zero_stock_unit_costs={}),opened['id'])
            report=fixture.office.draft(fixture.owner,fixture.project,'Servicebericht','Must remain exact on copied migration')
            signed=fixture.office.sign(fixture.owner,report['id'],report['content_hash'],'Synthetic signer',[[[.1,.1],[.8,.8]]]);pdf=fixture.office.pdf(fixture.owner,report['id'])
            tables=[r[0] for r in fixture.office.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if not r[0].startswith('business_schema_')]
            def snapshot(office):return {table:sorted((tuple(r) for r in office.db.execute('SELECT * FROM '+table)),key=repr) for table in tables}
            before=snapshot(fixture.office)
            with tempfile.TemporaryDirectory(prefix='synthetic-purchase-copy-') as temporary:
                path=Path(temporary)/'historical-copy.db'
                connection=sqlite3.connect(path);fixture.office.db.backup(connection);connection.close()
                patcher.stop()
                copy=Office(path)
                try:
                    self.assertEqual(snapshot(copy),before);self.assertEqual(snapshot(fixture.office),before)
                    self.assertEqual(copy.pdf(fixture.owner,report['id']),pdf);self.assertEqual(copy.report(fixture.owner,report['id']),signed)
                    self.assertTrue(business_schema.validate_integrity(copy));business_schema.ensure_schema(copy)
                    self.assertEqual(snapshot(copy),before);self.assertEqual(snapshot(fixture.office),before)
                    self.assertEqual(PurchaseChanges(copy).detail(fixture.owner,fixture.order['id'])['amendment_revision'],0)
                finally:copy.db.close()
        finally:fixture.doCleanups()


if __name__=='__main__':unittest.main()
