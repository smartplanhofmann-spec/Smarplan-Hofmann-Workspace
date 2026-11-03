"""Isolated additive annual module: real PG, MFA/HTTP, writers and restore.

The feature registry patch is test-local; production registration is separate.
Only the shared guarded disposable loopback fixture database is ever reset.
"""
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
import unittest
from unittest.mock import patch

import psycopg
from psycopg.conninfo import make_conninfo
import business_api
import business_schema
from business_payroll_annual_basis import PayrollAnnualBasis,protected_tables,validate_integrity
from business_payroll_facts import reference
from core import Problem
from online import release,test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import restore,complete_restore
from online.store import PostgresOffice,migrate
from online import test_business_payroll_facts_pg as fact_fixture
import test_business_payroll_annual_basis as annual_fixture

fixture=journey.fixture
req=fixture.request


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class PayrollAnnualPostgres(unittest.TestCase):
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call
    sources=fact_fixture.PayrollFactsPostgres.sources
    imported_details=annual_fixture.PayrollAnnualBasisTests.imported_details
    basis_details=annual_fixture.PayrollAnnualBasisTests.basis_details

    def setUp(self):
        names=business_schema.MODULE_NAMES
        if 'business_payroll_annual_basis' not in names:names+=('business_payroll_annual_basis',)
        schema=patch.object(business_schema,'MODULE_NAMES',names);schema.start();self.addCleanup(schema.stop)
        modules=business_api.MODULES
        if 'business_payroll_annual_basis' not in modules:modules+=('business_payroll_annual_basis',)
        routing=patch.object(business_api,'MODULES',modules);routing.start();self.addCleanup(routing.stop)
        self.previous=tuple(spec for spec in business_schema.registry() if spec.name!='business_payroll_annual_basis')
        if self._testMethodName.startswith('test_additive'):
            with patch.object(business_schema,'registry',return_value=self.previous),patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in self.previous)):
                journey.CustomerExecutionJourneyPostgres.setUp(self)
        else:journey.CustomerExecutionJourneyPostgres.setUp(self)
        self.owner=self.office.user(self.token)

    def workflow(self,data=None):
        data=data or self.sources();self.identity=data['identity'];self.data=data
        self.original=dict(id=data['file']['id'],revision=1,content_hash=data['file']['content_hash'])
        body=dict(employee_id=data['employee']['id'],employee_revision=data['employee']['revision'],kind='imported_period',
                  details=self.imported_details(),source_file_ids=[data['file']['id']])
        preview=self.call('POST','/business/payroll/annual-facts/preview',body).json
        command=body|req(revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        saved=self.call('POST','/business/payroll/annual-facts',command).json
        self.assertEqual(self.call('POST','/business/payroll/annual-facts',command).json,saved)
        return data|dict(command=command,saved=saved)

    def test_actual_mfa_http_private_and_offline_denial_with_runtime_acl(self):
        data=self.workflow();path='/business/payroll/annual-facts/'+data['saved']['id']
        self.call('GET',path,token=data['tech'],status=403)
        device=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET',path,token=device,status=403)
        self.call('GET',path,{},status=400)
        self.call('POST','/business/payroll/annual-facts?ignored=1',data['command'],status=400)
        for table in protected_tables():
            column='id' if table.endswith('events') else 'request_id'
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.assertRaisesRegex(psycopg.Error,'immutable payroll annual fact'):
                        with operator.transaction():
                            operator.execute('SET LOCAL ROLE "smartplan-migrator"');operator.execute(statement)
        self.assertTrue(validate_integrity(self.office));self.assertTrue(business_schema.validate_integrity(self.office))

    def test_two_pg_writers_accept_one_original_and_reject_stale_correction(self):
        data=self.workflow();barrier=threading.Barrier(2)
        command=data['command']|req(id=data['saved']['id'],revision=1,correction_reason='Originale parallel unabhängig bestätigt')
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10);return PayrollAnnualBasis(office).save(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0]['revision'],2)
        self.call('POST','/business/payroll/annual-facts',command|req(correction_reason='Stale distinct correction'),status=409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_annual_events').fetchone()[0],2)

    def test_additive_migration_actual_backup_restore_preserves_originals_and_accepted_receipt(self):
        with patch.object(business_schema,'registry',return_value=self.previous),patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in self.previous)):
            data=self.sources();before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        after=release.snapshot_fingerprint(fixture.DSN)
        for table,value in before.items():
            if table not in ('business_schema_state','business_schema_migrations','business_schema_events'):
                self.assertEqual(after[table],value,table)
        release.secure_database(fixture.DSN,test_mode=True);self.reopen();data=self.workflow(data)
        self.office.db.close();target=make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as operator:
            if operator.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            operator.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-payroll-annual-backup-') as directory:
                archive=backup(fixture.DSN,directory)
                self.assertTrue(restore(archive,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            runtime=make_conninfo(self.runtime,dbname='smartplan_release_check')
            verifier=PostgresOffice(runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=PayrollAnnualBasis(restored)
                self.assertEqual(api.save(self.owner,data['command']),data['saved'])
                self.assertEqual(api.resolve(self.owner,data['employee']['id'],reference(data['saved'])),data['saved'])
                self.assertEqual(bytes(api.hr._file(data['file']['id'])['original']),data['original'])
                self.assertTrue(validate_integrity(restored));self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:operator.execute('DROP DATABASE smartplan_release_check WITH (FORCE)')
        self.reopen()


if __name__=='__main__':unittest.main()
