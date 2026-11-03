"""A delivered physical device retains actual sources through its service history."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

from PIL import Image

from core import Office, Problem
from business_asset_provenance import AssetProvenance, dispatch, validate_integrity
from business_documents import Documents
from business_inventory import BusinessInventory
from business_maintenance import BusinessMaintenance
from business_operations import BusinessOperations
from business_purchasing import Purchasing
from business_organization import Organization


class AssetProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(lambda: self.office.db.close())
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Synthetischer Einsatz', 'Synthetischer Kunde')
        self.other = self.office.add_project(self.owner, 'Privates Projekt', 'Anderer Kunde')
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.clock = lambda: datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        self.api = AssetProvenance(self.office, clock=self.clock)
        self.inv = BusinessInventory(self.office, clock=self.clock)
        self.buy = Purchasing(self.office, clock=self.clock)
        self.ops = BusinessOperations(self.office, clock=self.clock)
        self.maint = BusinessMaintenance(self.office, clock=self.clock)
        for permission in ('inventory.read', 'inventory.write'):
            self.grant(permission)
        self.location = self.inv.save_location(self.owner, self.req(name='Synthetisches Lager'))
        self.article = Documents(self.office).save_article(self.owner, self.req(code='SYN-G', name='Synthetisches Gerät',
            kind='machine', unit='Stk.', unit_price_net='100', cost_price_net='40', tax_rate='19', tax_category='S', currency='EUR'))
        self.order = self.inv.save_order(self.owner, self.req(project_id=self.project, supplier_name='Synthetischer Lieferant',
            status='approved', items=[dict(article_id=self.article['id'], quantity='3')]))
        self.buy.confirm(self.owner, self.order['id'], self.req(source_revision=self.order['revision'], expected_receipt_revision=0,
            order_reference='SYN-ORDER-1', ordered_on='2026-11-01', confirmation=True))
        self.receipt = self.buy.receive(self.owner, self.order['id'], self.req(source_revision=self.order['revision'], expected_receipt_revision=0,
            receipt_reference='SYN-DELIVERY-1', received_on='2026-11-02', location_id=self.location['id'],
            lines=[dict(line_index=0, quantity='3', unit_cost_net='40')]))
        self.issue = self.inv.move(self.owner, self.req(kind='issue', article_id=self.article['id'], from_location_id=self.location['id'],
            project_id=self.project, quantity='2'))
        png = io.BytesIO()
        Image.new('RGB', (8, 8), '#aabbcc').save(png, format='PNG')
        self.original = png.getvalue()
        self.media = self.upload(self.project)
        self.document_body = self.req(media_id=self.media['id'], confirmed=True)
        self.document = self.api.attach_document(self.tech, self.receipt['id'], self.document_body)

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def req(self, **data):
        return dict(request_id=uuid.uuid4().hex, **data)

    def grant(self, permission, effect='allow'):
        with self.office.db:
            found = self.office.db.execute('SELECT id FROM business_permission_grants WHERE user_id=? AND permission=? AND scope=?',
                (self.tech['id'], permission, self.project)).fetchone()
            if found:
                self.office.db.execute('UPDATE business_permission_grants SET effect=?,revision=revision+1 WHERE id=?', (effect, found['id']))
                return
            self.office.db.execute('INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,?,?,1,?,?)',
                (uuid.uuid4().hex, self.tech['id'], permission, self.project, effect, self.owner['id'], self.api.now()))

    def error(self, status, function, *args):
        with self.assertRaises(Problem) as caught:
            function(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def upload(self, project):
        media = self.ops.new_media(self.owner, project, self.req(filename='Lieferschein.png', media_type='image/png',
            size=len(self.original), sha256=hashlib.sha256(self.original).hexdigest(), purpose='document', classification='operational'))
        self.ops.put_media_chunk(self.owner, project, media['id'], 0, self.original)
        self.ops.complete_media(self.owner, project, media['id'], self.req())
        return media

    def create_body(self, serial='SYN-SERIAL-1', **changes):
        return self.req(**{**dict(project_id=self.project, asset=dict(name='Geliefertes Testgerät', serial_number=serial,
            asset_type='Pumpe', location='Technikraum', notes='Synthetischer Test'), receipt_id=self.receipt['id'],
            line_index=0, issue_movement_id=self.issue['id'], quantity='1.0000', confirmed=True), **changes})

    def counts(self):
        return {name:self.office.db.execute('SELECT COUNT(*) AS n FROM ' + name).fetchone()['n'] for name in
                ('business_stock_movements', 'business_assets', 'business_maintenance_versions', 'business_maintenance_requests',
                 'business_asset_origins', 'business_asset_provenance_requests')}

    def test_delivered_asset_service_history_restart_and_retry_keep_one_origin_and_cost(self):
        before = self.counts()
        command = self.create_body()
        result = self.api.create(self.tech, command)
        self.assertEqual(self.api.create(self.tech, command), result)
        self.assertEqual(self.counts()['business_stock_movements'], before['business_stock_movements'])
        self.assertEqual(self.counts()['business_assets'], before['business_assets'] + 1)
        origin = result['origin']
        self.assertEqual((origin['receipt_id'], origin['issue_movement_id'], origin['order_id']),
                         (self.receipt['id'], self.issue['id'], self.order['id']))
        self.assertEqual(origin['document']['original']['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(self.inv.cost_report(self.owner, self.project)['material_actual_net'], '80.00')
        contract = self.maint.save_contract(self.owner, self.project, self.req(asset_id=result['id'], title='Regelmäßige Prüfung',
            anchor_date='2026-11-03', interval_unit='months', interval_count=12))
        visit = self.maint.schedule_due(self.owner, self.req(project_id=self.project, as_of='2026-11-03'))['items'][0]
        report = self.ops.save_entry(self.tech, self.project, 'service', self.req(title='Geräteprüfung', description='Geliefertes Gerät geprüft.'))
        report = self.ops.sign_entry(self.tech, self.project, report['id'], self.req(revision=1,
            expected_hash=report['content_hash'], signer='Synthetischer Kunde', strokes=[[[.1,.2],[.8,.5]]]))
        self.maint.complete_visit(self.tech, self.project, visit['id'], self.req(revision=1, report_id=report['id']))
        self.assertTrue(validate_integrity(self.office))
        self.office.db.close()
        self.office = Office(self.path)
        self.api = AssetProvenance(self.office, clock=self.clock)
        self.assertEqual(self.api.create(self.tech, command), result)
        history = BusinessMaintenance(self.office).history(self.tech, self.project, asset_id=result['id'])
        self.assertEqual(history[0]['asset_snapshot']['serial_number'], 'SYN-SERIAL-1')
        self.assertEqual(history[0]['contract_id'], contract['id'])
        self.assertEqual(history[0]['report_id'], report['id'])
        self.assertEqual(BusinessOperations(self.office).media_source(self.tech,self.project,self.media['id']), self.original)

    def test_original_binding_is_immutable_replayable_and_has_no_financial_values(self):
        self.assertEqual(self.api.attach_document(self.tech, self.receipt['id'], self.document_body), self.document)
        self.error(409, self.api.attach_document, self.tech, self.receipt['id'], self.req(media_id=self.media['id'], confirmed=True))
        encoded = json.dumps(self.api.sources(self.tech, self.project))
        for secret in ('unit_cost_net', 'cost_net', 'cost_price_net', 'unit_price_net', 'tax_rate'):
            self.assertNotIn(secret, encoded)
        self.assertEqual(self.api.sources(self.tech, self.project)['items'][0]['issues'][0]['available_quantity'], '2.0000')

    def test_receipt_and_issue_capacity_and_serial_identity_do_not_create_orphan_assets(self):
        self.api.create(self.tech, self.create_body())
        before = self.counts()
        for command in (self.create_body('syn-serial-1'), self.create_body('SYN-2', quantity='2'), self.create_body('', quantity='1')):
            self.error(400 if command['asset']['serial_number']=='' else 409, self.api.create, self.tech, command)
            self.assertEqual(self.counts(), before)
        second = self.api.create(self.tech, self.create_body('SYN-2'))
        self.assertEqual(second['origin']['quantity'], '1.0000')
        self.error(409, self.api.create, self.tech, self.create_body('SYN-3'))
        self.assertEqual(self.counts()['business_assets'], before['business_assets'] + 1)

    def test_existing_asset_can_bind_once_and_serial_cannot_be_rewritten(self):
        asset = self.maint.save_asset(self.tech, self.project, self.req(name='Bestehendes Gerät', serial_number='OLD-1'))
        command = self.req(asset_revision=asset['revision'], receipt_id=self.receipt['id'], line_index=0,
            issue_movement_id=self.issue['id'], quantity='1', confirmed=True)
        result = self.api.bind(self.tech, asset['id'], command)
        self.assertEqual(self.api.bind(self.tech, asset['id'], command), result)
        changed = self.maint.save_asset(self.tech, self.project, self.req(revision=1, name='Neuer Anzeigename', location='Anderer Raum'), asset['id'])
        self.assertEqual(self.api.bind(self.tech, asset['id'], command), result)
        self.error(409, self.maint.save_asset, self.tech, self.project, self.req(revision=changed['revision'], serial_number='OTHER'), asset['id'])
        self.assertTrue(validate_integrity(self.office))

    def test_bound_stock_cannot_be_returned_but_unbound_remainder_can(self):
        self.api.create(self.tech, self.create_body())
        body = self.req(kind='return', article_id=self.article['id'], to_location_id=self.location['id'],
            project_id=self.project, quantity='1', reversal_of=self.issue['id'])
        returned = self.inv.move(self.owner, body)
        self.assertEqual(self.inv.move(self.owner, body), returned)
        self.error(409, self.inv.move, self.owner, self.req(**{k:v for k,v in body.items() if k!='request_id'}))
        self.error(409, self.api.create, self.tech, self.create_body('SYN-2'))
        self.assertTrue(validate_integrity(self.office))

    def test_returns_before_binding_reduce_the_available_issue_quantity(self):
        self.inv.move(self.owner, self.req(kind='return', article_id=self.article['id'], to_location_id=self.location['id'],
            project_id=self.project, quantity='1.5', reversal_of=self.issue['id']))
        self.error(409, self.api.create, self.tech, self.create_body())
        self.assertEqual(self.counts()['business_assets'], 0)
        self.assertEqual(self.api.sources(self.tech, self.project)['items'][0]['issues'][0]['available_quantity'], '0.5000')

    def test_module_pause_preserves_history_and_blocks_new_commands_and_replays(self):
        command = self.create_body()
        result = self.api.create(self.tech, command)
        org = Organization(self.office)
        def settings(enabled):
            value = org.get(self.owner)
            body = self.req(revision=value['revision'], needs=value['needs'], modules={
                key:dict(visible=item['visibility_override'],enabled=item['enabled']) for key,item in value['modules'].items()})
            body['modules']['material']['enabled'] = enabled
            return body
        org.save(self.owner, settings(False))
        self.assertEqual(self.api.origin(self.tech,result['id']), result['origin'])
        self.error(423,self.api.create,self.tech,command)
        self.error(423,self.api.attach_document,self.tech,self.receipt['id'],self.document_body)
        org.save(self.owner, settings(True))
        self.assertEqual(self.api.create(self.tech,command),result)

    def test_fresh_permissions_and_classification_apply_before_successful_replay(self):
        command = self.create_body()
        result = self.api.create(self.tech, command)
        self.ops.annotate_media(self.owner, self.project, self.media['id'], self.req(revision=2, classification='financial'))
        self.error(403, self.api.create, self.tech, command)
        self.error(403, self.api.document, self.tech, self.receipt['id'])
        self.error(403, self.api.origin, self.tech, result['id'])
        self.assertFalse(self.api.sources(self.tech, self.project)['items'][0]['document_accessible'])
        self.assertTrue(validate_integrity(self.office))

    def test_revoked_project_and_scoped_rights_cannot_leak_sources_or_replay(self):
        command = self.create_body()
        result = self.api.create(self.tech, command)
        self.grant('inventory.write', effect='deny')
        self.error(403, self.api.create, self.tech, command)
        self.assertEqual(self.api.origin(self.tech, result['id']), result['origin'])
        self.office.assign(self.owner, self.project, self.tech['id'], remove=True)
        self.error(404, self.api.origin, self.tech, result['id'])
        self.error(404, self.api.sources, self.tech, self.project)

    def test_wrong_project_or_transfer_chain_never_implies_origin(self):
        foreign = self.maint.save_asset(self.owner, self.other, self.req(name='Privates Gerät', serial_number='PRIVATE'))
        self.error(404, self.api.bind, self.owner, foreign['id'], self.req(asset_revision=1, receipt_id=self.receipt['id'], line_index=0,
            issue_movement_id=self.issue['id'], quantity='1', confirmed=True))
        second = self.inv.save_location(self.owner, self.req(name='Zweites Lager'))
        self.inv.move(self.owner, self.req(kind='transfer', article_id=self.article['id'], from_location_id=self.location['id'],
            to_location_id=second['id'], quantity='1'))
        transferred = self.inv.move(self.owner, self.req(kind='issue', article_id=self.article['id'], from_location_id=second['id'],
            project_id=self.project, quantity='1'))
        self.error(409, self.api.create, self.tech, self.create_body(issue_movement_id=transferred['id']))

    def test_unknown_fields_confirmation_and_changed_request_are_rejected(self):
        self.error(400, self.api.create, self.tech, self.create_body(confirmed=False))
        self.error(400, self.api.create, self.tech, dict(self.create_body(), ignored='no'))
        command = self.create_body()
        self.api.create(self.tech, command)
        self.error(409, self.api.create, self.tech, dict(command, quantity='0.5'))
        for path,method,data in [('/assets/from-delivery','POST',dict(command,_query={'ignored':'1'})),
                                 ('/assets/origin-sources','GET',{'_query':{'project_id':[self.project,self.project]}})]:
            self.error(400, dispatch, self.office, self.tech, path, method, data)

    def test_sqlite_guards_reject_replace_update_and_delete(self):
        result = self.api.create(self.tech, self.create_body())
        for table,key,value in [('business_asset_origins','asset_id',result['id']),('business_delivery_documents','receipt_id',self.receipt['id'])]:
            row = dict(self.office.db.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(value,)).fetchone())
            for query,args in [('UPDATE '+table+' SET content_hash=? WHERE '+key+'=?',('0'*64,value)),
                               ('DELETE FROM '+table+' WHERE '+key+'=?',(value,)),
                               ('INSERT OR REPLACE INTO '+table+'('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))]:
                with self.assertRaises(sqlite3.IntegrityError):
                    with self.office.db:
                        self.office.db.execute(query,args)
        self.assertTrue(validate_integrity(self.office))

    def test_missing_or_corrupt_original_fails_closed(self):
        result = self.api.create(self.tech, self.create_body())
        with self.office.db:
            self.office.db.execute('UPDATE business_media SET original=? WHERE id=?', (b'corrupt', self.media['id']))
        self.error(500, self.api.origin, self.tech, result['id'])
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_competing_duplicate_create_commands_publish_one_asset_and_one_origin(self):
        command = self.create_body()
        barrier = threading.Barrier(2)
        def call():
            office = Office(self.path)
            try:
                barrier.wait(timeout=5)
                return AssetProvenance(office,clock=self.clock).create(self.tech,command)
            finally:
                office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = [future.result(timeout=15) for future in [pool.submit(call),pool.submit(call)]]
        self.assertEqual(values[0],values[1])
        self.assertEqual(self.counts()['business_asset_origins'],1)
        self.assertEqual(self.counts()['business_assets'],1)


if __name__ == '__main__':
    unittest.main()
