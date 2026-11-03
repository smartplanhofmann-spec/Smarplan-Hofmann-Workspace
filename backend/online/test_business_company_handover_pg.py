"""Real PostgreSQL bound instance, MVCC/fresh owner, migration and ZIP restore."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid
import zipfile

import business_schema
from business_company_handover import CompanyHandover,CHECKS,validate_integrity
from company_export_archive import verify
from core import Problem
from online import release,test_business_accounting_euer_pg as fixture
from online.instance import bind
from online.storage import Storage
from online.store import PostgresOffice,migrate,LOCK_ID
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve

req=fixture.req


@unittest.skipUnless(fixture.fixture.DSN,'Disposable loopback SMARTPLAN_TEST_DSN required')
class CompanyHandoverPostgres(unittest.TestCase):
    call=fixture.EuerPostgres.call
    login=fixture.EuerPostgres.login
    project=fixture.EuerPostgres.project
    issuer=fixture.EuerPostgres.issuer
    invoice=fixture.EuerPostgres.invoice

    def setUp(self):
        self.instance=None
        fixture.EuerPostgres.setUp(self)
        self.directory=tempfile.TemporaryDirectory(prefix='synthetic-company-pg-');self.addCleanup(self.directory.cleanup)
        self.instance=uuid.uuid4().hex
        self.storage_config={'server':{'path':str(Path(self.directory.name)/'company')}}
        operator=PostgresOffice(fixture.fixture.DSN)
        try:bind(operator,self.instance,'office.example.test',self.key,Storage(operator,self.key,'office.example.test',config=self.storage_config))
        finally:operator.db.close()
        self.reopen()
        self.owner=dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())

    def reopen(self):
        if not self.instance:return fixture.EuerPostgres.reopen(self)
        self.office.db.close();self.office=PostgresOffice(self.runtime);self.addCleanup(self.office.db.close)
        storage=Storage(self.office,self.key,'office.example.test',config=self.storage_config)
        self.app=create_app(office=self.office,key=self.key,host='office.example.test',storage=storage,instance_id=self.instance)
        self.client=self.app.test_client()

    def command(self):
        state=self.call('GET','/business/company-handover').json
        self.assertTrue(state['ready'],state['blockers'])
        return req(instance_id=self.instance,catalog_sha256=state['catalog_sha256'],reason='Synthetic operator-bound full company export',confirmation=True,sensitive_data_confirmed=True)

    def test_additive_migration_exact_originals_runtime_guards_and_dump_restore(self):
        self.office.db.close();full=business_schema.registry();prior=tuple(spec for spec in full if spec.name!='business_company_handover')
        with patch.object(business_schema,'registry',return_value=prior),patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in prior)):
            self.setUp();self.issuer();invoice=self.invoice(self.project(),'100.00')
            old_pdf=self.call('GET','/business/documents/'+invoice['id']+'/pdf').data
            before=release.snapshot_fingerprint(fixture.fixture.DSN);self.office.db.close()
        migrate(fixture.fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        after=release.snapshot_fingerprint(fixture.fixture.DSN)
        for table,value in before.items():
            if table not in ('business_schema_migrations','business_schema_state','business_schema_events'):self.assertEqual(after[table],value,table)
        release.secure_database(fixture.fixture.DSN,test_mode=True);self.reopen()
        command=self.command();result=self.call('POST','/business/company-handover/exports',command,status=201).json
        raw=self.call('GET','/business/company-handover/exports/'+result['id']+'/archive').data
        self.assertTrue(verify(raw,instance_id=self.instance)['valid'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            rows=[json.loads(line) for line in archive.read('data/business_document_archives.jsonl').splitlines()]
            self.assertEqual(archive.read(next(row for row in rows if row['document_id']==invoice['id'])['pdf']['$file']),old_pdf)
        with self.assertRaises(Exception):
            with self.office.db:self.office.db.execute('DELETE FROM business_company_exports')
        reviewed=self.call('POST','/business/company-handover/exit-reviews',req(instance_id=self.instance,expected_revision=0,export_id=result['id'],export_sha256=result['sha256'],
            checks={key:True for key in CHECKS},evidence='Synthetic operator received and checked archived evidence',reason='Synthetic exit preparation',confirmation=True),status=201).json
        self.assertEqual(reviewed['status'],'ready_for_operator_review')
        self.reopen();self.assertEqual(self.call('POST','/business/company-handover/exports',command,status=201).json,result)
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(bytes(CompanyHandover(restored).exported(self.owner,result['id'],action='archive')),raw)
                self.assertEqual(CompanyHandover(restored).state(self.owner)['exit_review'],reviewed)
                self.assertTrue(validate_integrity(restored))
            finally:restored.db.close()
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:self.assertEqual(CompanyHandover(restored).create(self.owner,command),result)
            finally:restored.db.close()

    def test_two_connections_snapshot_one_export_and_role_revocation_while_waiting_wins(self):
        command=self.command()
        def create(unused):
            office=PostgresOffice(self.runtime)
            try:return CompanyHandover(office).create(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_exports').fetchone()[0],1)
        command=self.command();waiting=threading.Event();pid=[]
        def blocked_export():
            office=PostgresOffice(self.runtime)
            try:
                pid.append(office.db.connection.info.backend_pid);waiting.set()
                try:return CompanyHandover(office).create(self.owner,command)
                except Problem as error:return error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.office.db:
                future=pool.submit(blocked_export);self.assertTrue(waiting.wait(5))
                deadline=time.monotonic()+5;blocked=False
                while time.monotonic()<deadline:
                    row=self.office.db.execute("SELECT 1 FROM pg_locks WHERE pid=? AND locktype='advisory' AND NOT granted",(pid[0],)).fetchone()
                    if row:blocked=True;break
                    time.sleep(.01)
                self.assertTrue(blocked,'Second export must actually be waiting before revocation.')
                self.office.db.execute("UPDATE users SET role='manager' WHERE id=?",(self.owner['id'],))
            self.assertEqual(future.result(timeout=10),403)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_exports').fetchone()[0],1)


if __name__=='__main__':unittest.main()
