"""Actual separated PG runtime, concurrent source commands and retained restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import unittest

import psycopg

import business_schema
from business_accounting_asset_openings import HistoricalAssets,TABLES,restore_horizon,public_source
from business_accounting_euer import EuerAccounting
from core import Problem,canonical
from online import test_business_accounting_euer_pg as euer,release
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
from test_accounting_asset_opening_rules import asset


fixture=euer.fixture
req=euer.req
BASE='/business/accounting/historical-assets'


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class HistoricalAssetPostgres(unittest.TestCase):
    reopen=euer.EuerPostgres.reopen
    login=euer.EuerPostgres.login
    call=euer.EuerPostgres.call
    profile=euer.EuerPostgres.profile
    post=euer.EuerPostgres.post

    def setUp(self):
        euer.EuerPostgres.setUp(self);self.actor=self.office.user(self.token);self.profile()
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0],'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))

    def original(self):
        raw=b'%PDF-1.4\nSynthetic PG acquisition original and complete historical depreciation\n%%EOF'
        command=req(asset_key='m-001',filename='synthetic-history.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        return self.call('POST',BASE+'/originals',command,status=201).json,command,raw

    def command(self,original,reason='Synthetic unchanged original linear history fully checked'):
        state=self.call('GET',BASE).json;year=int(self.today[:4])
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],asset_key='m-001',profile_ref=state['profile_ref'],
            opening_date=str(year)+'-01-01',status='active',reason=reason,
            asset=asset(acquired_on=str(year-2)+'-01-03',use_start=str(year-2)+'-01-03'),
            source=dict(original_id=original['id'],sha256=original['sha256'],position='Historic register row1',history_through=str(year-1)+'-12-31'))
        preview=self.call('POST',BASE+'/preview',body).json
        return req(**body,confirmation=True,preview_hash=preview['preview_hash'])

    def compete(self,commands):
        barrier=threading.Barrier(2)
        def worker(command):
            office=PostgresOffice(self.runtime)
            try:
                pid=office.db.execute('SELECT pg_backend_pid()').fetchone()[0];barrier.wait(timeout=15)
                try:return pid,201,HistoricalAssets(office).confirm(self.actor,command)
                except Problem as error:return pid,error.status,error.request_resolution
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,commands))
        self.assertNotEqual(results[0][0],results[1][0]);return [(status,value) for _,status,value in results]

    def test_two_connections_exact_replay_and_changed_commands_keep_one_version(self):
        original,_,_=self.original();command=self.command(original)
        first=self.compete([command,command]);self.assertEqual(first[0],first[1]);self.assertEqual(first[0][0],201)
        commands=[self.command(original,reason) for reason in ('Synthetic correction A','Synthetic correction B')]
        results=self.compete(commands);self.assertEqual(sorted(code for code,_ in results),[201,409])
        self.assertEqual(next(value for code,value in results if code==409),'not_accepted')
        self.assertEqual(restore_horizon(self.office)['table_counts'],dict(zip(TABLES,(1,2,3))))
        self.assertEqual(self.call('POST',BASE+'/confirm',command,status=201).json,first[0][1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_cash_events').fetchone()[0],0)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_original_and_all_three_tables_retain_runtime_immutable_acl_after_restart(self):
        original,upload,raw=self.original();command=self.command(original)
        entry=self.call('POST',BASE+'/confirm',command,status=201).json;scope=restore_horizon(self.office)
        self.assertEqual(self.call('GET',BASE+'/originals/'+original['id']).data,raw)
        for table in TABLES:
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
        self.assertEqual(restore_horizon(self.office),scope);self.reopen()
        self.assertEqual(self.call('POST',BASE+'/confirm',command,status=201).json,entry)
        self.assertEqual(self.call('POST',BASE+'/originals',upload,status=201).json,original)

    def test_populated_dump_restore_requires_new_scope_and_preserves_original_afa_and_exports(self):
        old_export,old_export_command=self.post('export',dict(year=int(self.today[:4])))
        old_artifact=self.call('GET','/business/accounting/euer/exports/'+old_export['id']).json
        original,upload,raw=self.original();command=self.command(original)
        entry=self.call('POST',BASE+'/confirm',command,status=201).json
        source=public_source(self.office,entry['id'])
        depreciation,depreciation_command=self.post('opening_depreciation',dict(asset_entry_id=entry['id'],source_hash=source['source_hash'],year=int(self.today[:4]),account='6220'))
        export,export_command=self.post('export',dict(year=int(self.today[:4])))
        artifact=self.call('GET','/business/accounting/euer/exports/'+export['id']).json
        self.assertEqual(artifact['report']['historical_assets'][0]['continuation']['amount'],'1200.00')
        scope=restore_horizon(self.office);fingerprints=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restored_report):
            restored=PostgresOffice(runtime)
            try:
                api=HistoricalAssets(restored)
                self.assertEqual(api.original(self.actor,original['id'])[0],raw)
                self.assertEqual(EuerAccounting(restored).exported(self.actor,export['id']),artifact)
                self.assertEqual(EuerAccounting(restored).exported(self.actor,old_export['id']),old_artifact)
                for call,args in ((api.confirm,(self.actor,command)),(api.upload_original,(self.actor,upload))):
                    with self.assertRaises(Problem) as blocked:call(*args)
                    self.assertEqual(blocked.exception.status,409)
                evidence=evidence_for(restored,restored_report)
                self.assertEqual(evidence['schema'],16);self.assertEqual(evidence['accounting_horizon']['historical_assets'],scope)
                with self.assertRaises(Problem) as denied:approve(restored,evidence)
                self.assertEqual(denied.exception.status,403)
            finally:restored.db.close()
            operator=PostgresOffice(target)
            try:
                old=deepcopy(evidence);old['schema']=13;old['accounting_horizon'].pop('opening_items');old['accounting_horizon'].pop('historical_assets');old['accounting_horizon']['schema_version']=12
                business_schema._validate_financial_accounting_horizon(old['accounting_horizon'],13)
                bad=deepcopy(evidence);bad['accounting_horizon']['historical_assets']['sha256']='0'*64
                before=release.snapshot_fingerprint(target)
                for value in (old,bad):
                    with self.assertRaises((ValueError,Problem)):approve(operator,value)
                    self.assertEqual(release.snapshot_fingerprint(target),before)
                accepted=approve(operator,evidence);self.assertTrue(accepted['reconciled']);self.assertEqual(approve(operator,evidence),accepted)
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=HistoricalAssets(restored);euer_api=EuerAccounting(restored)
                self.assertEqual(api.confirm(self.actor,command),entry);self.assertEqual(api.upload_original(self.actor,upload),original)
                for expected,receipt in ((old_export,old_export_command),(depreciation,depreciation_command),(export,export_command)):
                    self.assertEqual(euer_api.confirm(self.actor,receipt),expected)
                self.assertEqual(euer_api.exported(self.actor,export['id']),artifact)
                self.assertEqual(restore_horizon(restored),scope);self.assertTrue(business_schema.validate_integrity(restored))
                actual=release.snapshot_fingerprint(target)
                for table in TABLES+('business_euer_entries','business_euer_requests'):self.assertEqual(actual[table],fingerprints[table])
            finally:restored.db.close()


if __name__=='__main__':unittest.main()
