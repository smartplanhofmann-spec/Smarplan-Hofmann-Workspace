"""Actual PG/MFA supplier-return ledger, historical migration and restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import tempfile
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg.conninfo import make_conninfo
import business_schema
from business_documents import Documents,render_prepared
from business_inventory import BusinessInventory
from business_inventory_counts import InventoryCounts
from business_purchasing import Purchasing
from business_purchase_changes import PurchaseChanges,MAX_FILE,protected_tables
from online import release,test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice,migrate

fixture=journey.fixture

def req(**values):return dict(request_id=uuid.uuid4().hex,**values)


@unittest.skipUnless(fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class PurchaseChangesPostgres(unittest.TestCase):
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call
    def setUp(self):
        self.previous=tuple(spec for spec in business_schema.registry() if spec.name!='business_purchase_changes')
        if self._testMethodName.startswith('test_additive'):
            with patch.object(business_schema,'registry',return_value=self.previous), patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in self.previous)):journey.CustomerExecutionJourneyPostgres.setUp(self)
        else:journey.CustomerExecutionJourneyPostgres.setUp(self)
    def native(self):
        self.owner=self.office.user(self.token);self.project=self.office.add_project(self.owner,'Synthetic PG return project',customer='Synthetic PG customer')
        self.inventory=BusinessInventory(self.office);self.buy=Purchasing(self.office);self.changes=PurchaseChanges(self.office)
        self.article=Documents(self.office).save_article(self.owner,req(code='SYN-PG-RETURN',name='Synthetic actual material',kind='material',unit='C62',unit_price_net='8',cost_price_net='2',tax_rate='19',tax_category='S',currency='EUR',active=True))
        self.location=self.inventory.save_location(self.owner,req(name='Synthetic actual stock'))
        self.order=self.inventory.save_order(self.owner,req(project_id=self.project,supplier_name='Synthetic actual supplier',status='approved',items=[dict(article_id=self.article['id'],quantity='10')]))
        self.path='/business/purchasing/orders/'+self.order['id']
        self.confirm_body=req(source_revision=1,expected_receipt_revision=0,order_reference='ACTUAL-PG-ORDER',ordered_on=(self.now-timedelta(days=3)).date().isoformat(),confirmation=True)
        self.confirmed=self.call('POST',self.path+'/confirm',self.confirm_body).json
        self.first_body=req(source_revision=1,expected_receipt_revision=0,receipt_reference='ACTUAL-PG-DELIVERY-1',received_on=(self.now-timedelta(days=2)).date().isoformat(),location_id=self.location['id'],lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        self.first=self.call('POST',self.path+'/receipts',self.first_body,status=201).json
        self.second=self.call('POST',self.path+'/receipts',req(source_revision=1,expected_receipt_revision=1,receipt_reference='ACTUAL-PG-DELIVERY-2',received_on=(self.now-timedelta(days=1)).date().isoformat(),location_id=self.location['id'],lines=[dict(line_index=0,quantity='4',unit_cost_net='4')]),status=201).json
    def count(self,amount):
        counts=InventoryCounts(self.office)
        opened=counts.command(self.owner,'open',req(location_id=self.location['id'],article_ids=[self.article['id']],title='Synthetic actual PG count',counted_on=self.today,correction_of=None,reason='Actual physical units'))
        counted=counts.command(self.owner,'count',req(revision=1,lines=[dict(article_id=self.article['id'],quantity=amount,reason='Actual verified difference')]),opened['id'])
        return counts.command(self.owner,'approve',req(revision=2,confirmed=True,zero_stock_unit_costs={}),opened['id'])
    def basis(self):
        detail=self.call('GET',self.path+'/changes').json
        return dict(source_revision=detail['source_revision'],expected_receipt_revision=detail['receipt_revision'],expected_amendment_revision=detail['amendment_revision'],expected_return_revision=detail['return_revision'],source_sha256=detail['source_sha256'])
    def body(self,action,**values):
        data=dict(**self.basis(),**values);preview=self.call('POST',self.path+'/'+action+'/preview',data).json
        return req(**data,preview_sha256=preview['preview_sha256'],confirmation=True)
    def invoice(self):
        docs=Documents(self.office)
        docs.save_settings(self.owner,req(revision=0,company_name='Synthetic Seller',address_line='Synthetic Street 1',postal_code='10115',city='Berlin',country='DE',vat_id='DE123456789',email='seller@example.test',issuer_mode='own',issuing_enabled=True,cutover_ack=True,cutover_date='2025-01-01',einvoice_format='none'))
        draft=docs.create(self.owner,req(project_id=self.project,kind='invoice',title='Actual synthetic immutable invoice',issue_date=self.today,due_date=(self.now+timedelta(days=14)).date().isoformat(),buyer=dict(name='Synthetic Buyer',address_line='Synthetic Street 2',postal_code='10117',city='Berlin',country='DE',email='buyer@example.test'),positions=[dict(description='Synthetic service',quantity='1',unit='HUR',unit_price_net='100.00',tax_rate='19',kind='labor')]))
        prepared=docs.prepare_finalization(self.owner,draft['id'],draft['revision']);issued=docs.finalize(self.owner,draft['id'],render_prepared(prepared),uuid.uuid4().hex)
        self.assertEqual(issued['archive_security'],'postgresql_runtime_separated')
        return issued,docs.archive(self.owner,draft['id'],'pdf')
    def workflow(self):
        self.native();self.count('12')
        raw=b'%PDF-1.7\n'+b'x'*(MAX_FILE-9)
        upload=req(filename='actual-supplier-return.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        evidence=self.call('POST',self.path+'/change-files',upload).json
        self.assertEqual(self.call('POST',self.path+'/change-files',upload).json,evidence)
        self.assertEqual(self.call('GET',self.path+'/change-files/'+evidence['id']+'/original').data,raw)
        self.call('POST',self.path+'/change-files',req(filename='too-big.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'x'*(MAX_FILE+1)).decode()),status=413)
        body=self.body('supplier-returns',reference='ACTUAL-PG-RETURN-1',returned_on=self.today,reason='Actual externally performed physical return',evidence_id=evidence['id'],lines=[dict(receipt_id=self.first['id'],line_index=0,quantity='1'),dict(receipt_id=self.second['id'],line_index=0,quantity='1')])
        def returned():
            office=PostgresOffice(self.runtime)
            try:return PurchaseChanges(office).confirm(self.owner,self.order['id'],'supplier-returns',body)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:returned(),range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_supplier_returns').fetchone()[0],1)
        self.assertEqual(self.call('POST',self.path+'/supplier-returns',body).json,results[0])
        self.count('9')
        second_body=self.body('supplier-returns',reference='ACTUAL-PG-RETURN-2',returned_on=self.today,reason='Second actual physical return',evidence_id=evidence['id'],lines=[dict(receipt_id=self.first['id'],line_index=0,quantity='2')])
        second=self.call('POST',self.path+'/supplier-returns',second_body).json
        issue=self.inventory.move(self.owner,req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='7'))
        self.assertEqual(issue['cost_net'],'19.6000')
        amend_body=self.body('amendments',kind='replacement',reference='ACTUAL-PG-REPLACEMENT',effective_on=self.today,reason='Four replacement units explicitly agreed',evidence_id=evidence['id'],lines=[dict(line_index=0,authorized_quantity='14')])
        amendment=self.call('POST',self.path+'/amendments',amend_body).json
        replacement=req(source_revision=1,expected_receipt_revision=2,receipt_reference='ACTUAL-PG-REPLACEMENT-DELIVERY',received_on=self.today,location_id=self.location['id'],lines=[dict(line_index=0,quantity='4',unit_cost_net='3')])
        self.call('POST',self.path+'/receipts',replacement,status=409);replacement['expected_amendment_revision']=1
        delivered=self.call('POST',self.path+'/receipts',replacement,status=201).json
        self.assertEqual(self.call('POST',self.path+'/receipts',self.first_body,status=201).json,self.first)
        self.assertEqual(self.call('POST',self.path+'/supplier-returns',body).json,results[0])
        self.assertEqual(self.call('POST',self.path+'/amendments',amend_body).json,amendment)
        detail=self.call('GET',self.path+'/changes').json;self.assertEqual(detail['items'][0]['retained_quantity'],'10.0000')
        self.assertEqual(self.inventory.cost_report(self.owner,self.project)['material_actual_net'],'19.60')
        issued,pdf=self.invoice();business_schema.validate_integrity(self.office)
        return dict(path=self.path,order_id=self.order['id'],evidence=evidence,raw=raw,upload=upload,body=body,result=results[0],second_body=second_body,second=second,amend_body=amend_body,amendment=amendment,replacement=replacement,delivered=delivered,detail=detail,issued=issued,pdf=pdf)

    def test_real_mfa_http_concurrent_return_shared_count_replay_current_rights_and_runtime_acl(self):
        data=self.workflow();path=data['path']
        self.call('GET',path+'/changes',{'ignored':True},status=400)
        self.call('POST',path+'/supplier-returns?ignored=1',data['body'],status=400)
        self.call('POST',path+'/supplier-returns',dict(data['body'],reason='Different original request'),status=409)
        self.call('POST','/users',dict(email='return-tech-pg@example.test',password='Synthetic-return-tech-password-123',role='technician'),status=201)
        token=self.login('return-tech-pg@example.test','Synthetic-return-tech-password-123')
        self.call('GET',path+'/changes',token=token,status=404);self.call('POST',path+'/supplier-returns',data['body'],token=token,status=404)
        device=self.call('POST','/business/offline/access',{},status=201).json['token'];self.call('GET',path+'/changes',token=device,status=403)
        for table in protected_tables():
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as migrator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.subTest(table=table,statement=statement),self.assertRaisesRegex(psycopg.Error,'immutable purchase change'):
                        with migrator.transaction():migrator.execute('SET LOCAL ROLE "smartplan-migrator"');migrator.execute(statement)
        self.reopen();self.assertEqual(self.call('POST',path+'/supplier-returns',data['body']).json,data['result']);business_schema.validate_integrity(self.office)

    def test_actual_dump_restore_preserves_shared_stock_order_originals_and_issued_invoice(self):
        data=self.workflow();actor,runtime=self.owner,self.runtime
        before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check');release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='purchase-changes-pg-restore-') as directory:
                saved=backup(fixture.DSN,directory);self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_runtime=make_conninfo(runtime,dbname='smartplan_release_check');verifier=PostgresOffice(restored_runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            recovered=PostgresOffice(restored_runtime)
            try:
                api=PurchaseChanges(recovered)
                self.assertEqual(api.confirm(actor,data['order_id'],'supplier-returns',data['body']),data['result'])
                self.assertEqual(api.confirm(actor,data['order_id'],'supplier-returns',data['second_body']),data['second'])
                self.assertEqual(api.confirm(actor,data['order_id'],'amendments',data['amend_body']),data['amendment'])
                self.assertEqual(api.upload(actor,data['order_id'],data['upload']),data['evidence'])
                self.assertEqual(bytes(api.file(data['order_id'],data['evidence']['id'])['content']),data['raw'])
                self.assertEqual(api.detail(actor,data['order_id']),data['detail'])
                self.assertEqual(Purchasing(recovered).receive(actor,data['order_id'],data['replacement']),data['delivered'])
                self.assertEqual(Documents(recovered).archive(actor,data['issued']['id'],'pdf'),data['pdf'])
                business_schema.validate_integrity(recovered);after=release.snapshot_fingerprint(target)
                for table in (*protected_tables(),'business_stock_movements','business_inventory_adjustments','business_purchase_receipts','business_document_archives'):
                    self.assertEqual(after[table],before[table],table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
            finally:recovered.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')

    def test_additive_migration_preserves_historical_partial_delivery_count_and_actual_issued_invoice(self):
        with patch.object(business_schema,'registry',return_value=self.previous), patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in self.previous)):
            self.native();self.count('9');issued,pdf=self.invoice();self.office.db.close()
            before=release.snapshot_fingerprint(fixture.DSN);self.assertNotIn('business_supplier_returns',before)
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        release.secure_database(fixture.DSN,test_mode=True);self.reopen()
        after=release.snapshot_fingerprint(fixture.DSN)
        for table,value in before.items():
            if not table.startswith('business_schema_'):self.assertEqual(after[table],value,table)
        self.assertEqual(Documents(self.office).archive(self.owner,issued['id'],'pdf'),pdf)
        self.assertEqual(self.call('POST',self.path+'/confirm',self.confirm_body).json,self.confirmed)
        self.assertEqual(self.call('POST',self.path+'/receipts',self.first_body,status=201).json,self.first)
        self.assertEqual(self.call('GET',self.path+'/changes').json['amendment_revision'],0)
        business_schema.validate_integrity(self.office)


if __name__=='__main__':unittest.main()
