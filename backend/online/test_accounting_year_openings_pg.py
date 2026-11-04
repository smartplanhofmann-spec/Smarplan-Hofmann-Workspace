"""Actual PG year-source receipts, concurrency, immutable ACL and populated restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import unittest
import uuid
import psycopg
import business_schema
from business_accounting_year_openings import YearValues,TABLES,restore_horizon,public_source
from business_accounting_open_items import OpeningItems
from business_accounting_euer import EuerAccounting
from core import Problem
from online import test_accounting_open_items_pg as old,release
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve

fixture=old.fixture
req=old.req
BASE='/business/accounting/year-values'

@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class YearValuesPostgres(unittest.TestCase):
    reopen=old.OpeningItemPostgres.reopen
    login=old.OpeningItemPostgres.login
    call=old.OpeningItemPostgres.call
    post=old.OpeningItemPostgres.post
    original=old.OpeningItemPostgres.original
    command=old.OpeningItemPostgres.command
    payment_command=old.OpeningItemPostgres.payment_command
    classify_payment=old.OpeningItemPostgres.classify

    def setUp(self):
        old.OpeningItemPostgres.setUp(self)
        self.assertEqual(self.year,2026,'Explicit 2026 original-value contract fixture')
        state=self.call('GET','/business/accounting/profile').json
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic under-year software cutover',evidence_reference='Synthetic continuous original EÜR method',profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01'))
        preview=self.call('POST','/business/accounting/profile/preview',body).json
        self.call('POST','/business/accounting/profile/confirm',req(**body,confirmation=True,preview_hash=preview['preview_hash']),status=201)
        helper=old.item_fixture.OpeningItemWorkflow('runTest');helper.original=self.original
        payload=helper.item('old-item','payable');payload.update(invoice_date='2026-06-10',service_date='2026-06-10',invoice_received_date='2026-06-11',history_through='2026-10-31')
        payload['prior_input_vat'].update(entitlement_date='2026-06-11',declared_period='2026-06',deducted_on='2026-07-10')
        payload['prior_payments']=[dict(date='2026-08-20',reference='Actual August old part',gross='59.50',net='50.00',tax='9.50',proof=payload['cutover_proof'])]
        self.item_command=self.command('item','old-item',payload);self.item=self.call('POST',old.BASE+'/confirm',self.item_command,status=201).json
        raw=b'%PDF-1.4\nSynthetic independent complete original Jan-Oct journal\n%%EOF';self.year_upload=req(entity_key='2026',filename='original-journal.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        self.year_original=self.call('POST',BASE+'/originals',self.year_upload,status=201).json;self.year_raw=raw
        self.payload=dict(status='active',coverage={'from':'2026-01-01','through':'2026-10-31'},sources=[dict(kind='opening_item',entry_id=self.item['id'],entry_hash=self.item['content_hash'],accounts=dict(net='5400',tax='1406',input_vat='1406'),cash_entry_keys=['OLD-081'],vat_entry_key='OLD-061')],
            controls=[dict(ledger='euer',category='materials',account='5400',amount='-50.00'),dict(ledger='euer',category='paid_input_vat',account='1406',amount='-9.50'),dict(ledger='vat',category='input_vat',account='1406',amount='-19.00')],ledger_proof=dict(original_id=self.year_original['id'],sha256=self.year_original['sha256']),attestations=dict(continuous_method=True,original_journal_complete=True,no_unsupported_values=True))

    def year_command(self,payload=None):
        state=self.call('GET',BASE).json;body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],entity_key='2026',profile_ref=state['profile_ref'],operation='year_values',payload=payload or self.payload,reason='Actual original yearly journal and exact controls reviewed')
        preview=self.call('POST',BASE+'/preview',body).json
        return req(**body,confirmation=True,preview_hash=preview['preview_hash'])

    def classify(self,entry):
        source=public_source(self.office,entry['entity_key'])
        return self.post('opening_year_values',dict(year=source['id'],revision=source['revision'],source_hash=source['source_hash']))

    def compete(self,commands):
        barrier=threading.Barrier(2)
        def worker(command):
            office=PostgresOffice(self.runtime)
            try:
                pid=office.db.execute('SELECT pg_backend_pid()').fetchone()[0];barrier.wait(timeout=15)
                try:return pid,201,YearValues(office).confirm(self.actor,command)
                except Problem as error:return pid,error.status,error.request_resolution
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,commands))
        self.assertNotEqual(results[0][0],results[1][0]);return [(status,value) for _,status,value in results]

    def test_actual_connections_duplicate_ack_and_competing_period_revision(self):
        command=self.year_command();results=self.compete([command,command]);self.assertEqual(results[0],results[1]);self.assertEqual(results[0][0],201)
        commands=[self.year_command(),self.year_command()];results=self.compete(commands)
        self.assertEqual(sorted(status for status,_ in results),[201,409]);self.assertEqual(next(value for status,value in results if status==409),'not_accepted')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[1]).fetchone()[0],2)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_immutable_acl_restart_and_original_receipts(self):
        command=self.year_command();entry=self.call('POST',BASE+'/confirm',command,status=201).json;self.classify(entry);scope=restore_horizon(self.office)
        for table in TABLES:
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
        self.assertEqual(restore_horizon(self.office),scope);self.reopen()
        self.assertEqual(self.call('POST',BASE+'/confirm',command,status=201).json,entry)
        self.assertEqual(self.call('POST',BASE+'/originals',self.year_upload,status=201).json,self.year_original)
        self.assertEqual(self.call('GET',BASE+'/originals/'+self.year_original['id']).data,self.year_raw)

    def test_populated_actual_dump_restore_preserves_old_and_new_year_exports_and_cash(self):
        old_export,old_command=self.post('export',dict(year=2026));old_artifact=self.call('GET','/business/accounting/euer/exports/'+old_export['id']).json
        command=self.year_command();entry=self.call('POST',BASE+'/confirm',command,status=201).json;posted,posted_command=self.classify(entry)
        paid_command=self.payment_command(self.item,'59.50');paid=self.call('POST',old.BASE+'/confirm',paid_command,status=201).json;cash,cash_command=self.classify_payment(paid)
        export,export_command=self.post('export',dict(year=2026));artifact=self.call('GET','/business/accounting/euer/exports/'+export['id']).json
        self.assertEqual((artifact['report']['totals']['confirmed_expenses'],artifact['report']['totals']['confirmed_input_vat'],artifact['report']['totals']['euer_surplus']),('119.00','19.00','-119.00'))
        self.assertEqual([m['amount'] for m in artifact['report']['cash_movements']],['59.50'])
        scope=restore_horizon(self.office);fingerprints=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            restored=PostgresOffice(runtime)
            try:
                api=YearValues(restored);euer_api=EuerAccounting(restored)
                self.assertEqual(euer_api.exported(self.actor,old_export['id']),old_artifact);self.assertEqual(euer_api.exported(self.actor,export['id']),artifact)
                self.assertEqual(api.original(self.actor,self.year_original['id'])[0],self.year_raw)
                for original,upload,raw in self.uploads:self.assertEqual(OpeningItems(restored).original(self.actor,original['id'])[0],raw)
                with self.assertRaises(Problem) as denied:api.confirm(self.actor,command)
                self.assertEqual(denied.exception.status,409)
                evidence=evidence_for(restored,report);self.assertEqual(evidence['schema'],16);self.assertEqual(evidence['accounting_horizon']['year_values'],scope)
                with self.assertRaises(Problem) as denied:approve(restored,evidence)
                self.assertEqual(denied.exception.status,403)
            finally:restored.db.close()
            operator=PostgresOffice(target)
            try:
                old_scope=deepcopy(evidence);old_scope['schema']=15;old_scope['accounting_horizon'].pop('year_values');old_scope['accounting_horizon']['schema_version']=14
                bad=deepcopy(evidence);bad['accounting_horizon']['year_values']['sha256']='0'*64
                before=release.snapshot_fingerprint(target)
                for value in (old_scope,bad):
                    with self.assertRaises((ValueError,Problem)):approve(operator,value)
                    self.assertEqual(release.snapshot_fingerprint(target),before)
                accepted=approve(operator,evidence);self.assertTrue(accepted['reconciled']);self.assertEqual(approve(operator,evidence),accepted)
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=YearValues(restored);euer_api=EuerAccounting(restored)
                self.assertEqual(api.confirm(self.actor,command),entry);self.assertEqual(OpeningItems(restored).confirm(self.actor,self.item_command),self.item);self.assertEqual(OpeningItems(restored).confirm(self.actor,paid_command),paid)
                for expected,body in ((old_export,old_command),(posted,posted_command),(cash,cash_command),(export,export_command)):self.assertEqual(euer_api.confirm(self.actor,body),expected)
                self.assertEqual(restore_horizon(restored),scope);self.assertTrue(business_schema.validate_integrity(restored))
                actual=release.snapshot_fingerprint(target)
                for table in TABLES+('business_euer_entries','business_euer_requests'):self.assertEqual(actual[table],fingerprints[table])
            finally:restored.db.close()

if __name__=='__main__':unittest.main()
