"""Real PostgreSQL runtime, competing actual payments and populated dump/restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import unittest
import uuid
import psycopg
import business_schema
from business_accounting_open_items import OpeningItems,TABLES,restore_horizon,public_source
from business_accounting_euer import EuerAccounting
from core import Problem
from online import test_business_accounting_euer_pg as euer,release
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
import test_business_accounting_open_items as item_fixture

fixture=euer.fixture
req=euer.req
BASE='/business/accounting/open-items'

@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class OpeningItemPostgres(unittest.TestCase):
    reopen=euer.EuerPostgres.reopen
    login=euer.EuerPostgres.login
    call=euer.EuerPostgres.call
    post=euer.EuerPostgres.post

    def setUp(self):
        euer.EuerPostgres.setUp(self);self.actor=self.office.user(self.token);self.year=int(self.today[:4])
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0],'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        state=self.call('GET','/business/accounting/profile').json
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic proven ongoing old EÜR/Ist activity',evidence_reference='Synthetic historical method originals',profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from=str(self.year-1)+'-01-01',bookkeeping_start=str(self.year)+'-01-01'))
        preview=self.call('POST','/business/accounting/profile/preview',body).json
        self.call('POST','/business/accounting/profile/confirm',req(**body,confirmation=True,preview_hash=preview['preview_hash']),status=201)
        self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='OLD',name='Synthetic old-item money account',kind='bank'),status=201).json
        self.uploads=[]

    def original(self,key,marker):
        raw=('%PDF-1.4\nSynthetic PG '+marker+'\n%%EOF').encode()
        command=req(entity_key=key,filename='old.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        original=self.call('POST',BASE+'/originals',command,status=201).json;self.uploads.append((original,command,raw))
        return dict(original_id=original['id'],sha256=original['sha256'])

    def command(self,operation,key,payload):
        state=self.call('GET',BASE).json
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],entity_key=key,profile_ref=state['profile_ref'],operation=operation,payload=payload,reason='Synthetic historical original and actual amounts checked')
        preview=self.call('POST',BASE+'/preview',body).json
        return req(**body,confirmation=True,preview_hash=preview['preview_hash'])

    def item(self,direction='payable',prior=False):
        helper=item_fixture.OpeningItemWorkflow('runTest');helper.original=self.original
        payload=helper.item('old-item',direction,prior=prior);old=str(self.year-1)
        payload.update(invoice_date=old+'-11-10',service_date=old+'-11-10',invoice_received_date=old+'-11-11',history_through=old+'-12-31')
        for part in payload['prior_payments']:part['date']=old+'-12-20'
        if payload['prior_input_vat']:payload['prior_input_vat'].update(entitlement_date=old+'-11-11',declared_period=old+'-11',deducted_on=old+'-12-10')
        command=self.command('item','old-item',payload)
        return self.call('POST',BASE+'/confirm',command,status=201).json,command

    def payment_command(self,item,amount='119.00'):
        key=uuid.uuid4().hex
        return self.command('payment',key,dict(status='active',item_key=item['entity_key'],item_id=item['id'],item_hash=item['content_hash'],date=self.today,amount=amount,account_id=self.account['id'],account_revision=1,evidence_reference='Actual old-item PG transfer '+key,proof=self.original(item['entity_key'],'actual transfer '+key)))

    def classify(self,payment):
        source=public_source(self.office,payment['entity_key'])
        return self.post('opening_item_cash',dict(payment_id=source['id'],revision=source['revision'],source_hash=source['source_hash'],net_account='4400' if source['direction']=='in' else '5400',tax_account='3806' if source['direction']=='in' else '1406'))

    def compete(self,commands):
        barrier=threading.Barrier(2)
        def worker(command):
            office=PostgresOffice(self.runtime)
            try:
                pid=office.db.execute('SELECT pg_backend_pid()').fetchone()[0];barrier.wait(timeout=15)
                try:return pid,201,OpeningItems(office).confirm(self.actor,command)
                except Problem as error:return pid,error.status,error.request_resolution
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,commands))
        self.assertNotEqual(results[0][0],results[1][0]);return [(status,value) for _,status,value in results]

    def test_real_connections_exact_lost_ack_and_competing_rest_consumption(self):
        item,_=self.item('receivable');first=self.payment_command(item,'59.50')
        repeated=self.compete([first,first]);self.assertEqual(repeated[0],repeated[1]);self.assertEqual(repeated[0][0],201)
        commands=[self.payment_command(item,'59.50'),self.payment_command(item,'59.50')]
        results=self.compete(commands);self.assertEqual(sorted(status for status,_ in results),[201,409]);self.assertEqual(next(value for status,value in results if status==409),'not_accepted')
        self.assertEqual(self.call('GET',BASE).json['items'][0]['remaining'],'0.00')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[1]).fetchone()[0],3)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_originals_immutable_acl_and_current_payment_after_actual_restart(self):
        item,item_command=self.item();command=self.payment_command(item);payment=self.call('POST',BASE+'/confirm',command,status=201).json
        self.classify(payment);scope=restore_horizon(self.office)
        for table in TABLES:
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
        self.assertEqual(restore_horizon(self.office),scope);self.reopen()
        self.assertEqual(self.call('POST',BASE+'/confirm',command,status=201).json,payment)
        self.assertEqual(self.call('POST',BASE+'/confirm',item_command,status=201).json,item)
        for original,upload,raw in self.uploads:
            self.assertEqual(self.call('POST',BASE+'/originals',upload,status=201).json,original)
            self.assertEqual(self.call('GET',BASE+'/originals/'+original['id']).data,raw)

    def test_populated_actual_dump_restore_keeps_old_exports_all_originals_and_no_repeated_input_vat(self):
        old_export,old_command=self.post('export',dict(year=self.year));old_artifact=self.call('GET','/business/accounting/euer/exports/'+old_export['id']).json
        item,item_command=self.item();payment_command=self.payment_command(item);payment=self.call('POST',BASE+'/confirm',payment_command,status=201).json
        posted,posted_command=self.classify(payment);export,export_command=self.post('export',dict(year=self.year));artifact=self.call('GET','/business/accounting/euer/exports/'+export['id']).json
        self.assertEqual((artifact['report']['totals']['confirmed_expenses'],artifact['report']['totals']['confirmed_input_vat']),('119.00','0.00'))
        scope=restore_horizon(self.office);fingerprints=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            restored=PostgresOffice(runtime)
            try:
                api=OpeningItems(restored);euer_api=EuerAccounting(restored)
                self.assertEqual(euer_api.exported(self.actor,old_export['id']),old_artifact);self.assertEqual(euer_api.exported(self.actor,export['id']),artifact)
                for original,upload,raw in self.uploads:self.assertEqual(api.original(self.actor,original['id'])[0],raw)
                with self.assertRaises(Problem) as denied:api.confirm(self.actor,payment_command)
                self.assertEqual(denied.exception.status,409)
                evidence=evidence_for(restored,report);self.assertEqual(evidence['schema'],16);self.assertEqual(evidence['accounting_horizon']['opening_items'],scope)
                with self.assertRaises(Problem) as denied:approve(restored,evidence)
                self.assertEqual(denied.exception.status,403)
            finally:restored.db.close()
            operator=PostgresOffice(target)
            try:
                old=deepcopy(evidence);old['schema']=14;old['accounting_horizon'].pop('year_values');old['accounting_horizon'].pop('opening_items');old['accounting_horizon']['schema_version']=13
                business_schema._validate_financial_accounting_horizon(old['accounting_horizon'],14)
                bad=deepcopy(evidence);bad['accounting_horizon']['opening_items']['sha256']='0'*64
                before=release.snapshot_fingerprint(target)
                for value in (old,bad):
                    with self.assertRaises((ValueError,Problem)):approve(operator,value)
                    self.assertEqual(release.snapshot_fingerprint(target),before)
                accepted=approve(operator,evidence);self.assertTrue(accepted['reconciled']);self.assertEqual(approve(operator,evidence),accepted)
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=OpeningItems(restored);euer_api=EuerAccounting(restored)
                for expected,command in ((item,item_command),(payment,payment_command)):self.assertEqual(api.confirm(self.actor,command),expected)
                for expected,command in ((old_export,old_command),(posted,posted_command),(export,export_command)):self.assertEqual(euer_api.confirm(self.actor,command),expected)
                self.assertEqual(restore_horizon(restored),scope);self.assertTrue(business_schema.validate_integrity(restored))
                actual=release.snapshot_fingerprint(target)
                for table in TABLES+('business_euer_entries','business_euer_requests'):self.assertEqual(actual[table],fingerprints[table])
            finally:restored.db.close()

if __name__=='__main__':unittest.main()
