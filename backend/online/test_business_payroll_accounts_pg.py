"""MFA/HTTP/SQL-role/actual-restore proof for statutory account evidence."""
import tempfile
import unittest

import psycopg
from psycopg.conninfo import make_conninfo
import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts,protected_tables,validate_integrity
from payroll_de_2026 import month_range
from business_personnel_workflow import _sha
import test_business_payroll_accounts as domain
from test_payroll_de_2026 import profile
from online import test_business_payroll_pg as payroll_pg,release
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice

fixture=payroll_pg.fixture
request=payroll_pg.request


@unittest.skipUnless(fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class PayrollAccountsPostgres(unittest.TestCase):
    setUp=payroll_pg.RegularPayrollPostgres.setUp
    reopen=payroll_pg.RegularPayrollPostgres.reopen
    login=payroll_pg.RegularPayrollPostgres.login
    call=payroll_pg.RegularPayrollPostgres.call

    def workflow(self):
        data=payroll_pg.RegularPayrollPostgres.workflow(self)
        employee=data['hr']['employee'];file=data['hr']['file']
        self.assertEqual(self.today[:7],'2026-11','The synthetic two-month fixture is pinned to November 2026')
        def save(kind,details,**changes):
            return self.call('POST','/business/payroll/account-records',request(employee_id=employee['id'],kind=kind,
                revision=0,source_file_id=file['id'],confirmed=True,details=details,**changes)).json
        details=domain.PayrollAccountTests.identity_details(self,data,employment_from='2026-10-01',employment_to='2026-11-30',
            valid_from=data['profile']['profile']['effective_from'])
        identity=save('identity',details)
        payment=save('payment',dict(run_id=data['run']['id'],run_revision=1,identity_id=identity['id'],identity_revision=1,
            payments=[dict(paid_on=self.today,amount_minor=313009,payment_reference='SYN-PG-WAGE-NOV')],
            tax_free_payments_minor=1999,tax_free_basis='Synthetic reviewed travel expense original',standard_case_confirmed=True))
        prior=self.call('POST','/business/payroll/profiles',request(employee_id=employee['id'],revision=0,
            profile=profile('regular',effective_from='2026-01-01',regular_annual_gross_minor=6000000,
                health_additional_percent='2.90',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0),
            source_file_id=file['id'],confirmed=True)).json
        prior_identity=save('identity',domain.PayrollAccountTests.identity_details(self,{**data,'profile':prior},
            employment_from='2026-10-01',employment_to='2026-11-30'))
        carry=save('carryover',dict(month='2026-10',profile_id=prior['id'],profile_revision=1,
            identity_id=prior_identity['id'],identity_revision=1,gross_minor=500000,expected_net_minor=313009,
            expected_employee_tax_minor=78241,expected_employee_social_total_minor=108750,
            expected_employer_social_total_minor=105750,expected_employer_total_minor=619200,
            payments=[dict(paid_on='2026-10-31',amount_minor=313009,payment_reference='SYN-PG-PRIOR-OCT')],
            tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True,status='active'))
        query='?employee_id='+employee['id']+'&year=2026'
        ledger=self.call('GET','/business/payroll/ledger'+query).json
        self.assertEqual(ledger['ledger']['totals']['gross_minor'],1000000)
        self.assertEqual(ledger['ledger']['totals']['net_minor'],626018)
        self.assertEqual(ledger['ledger']['recorded_tax_free_payments_minor'],1999)
        self.assertTrue(ledger['ledger']['statutory_wage_account_complete'])
        exports={}
        for kind in ('pdf','csv','json'):
            exports[kind]=self.call('GET','/business/payroll/ledger/'+kind+query+'&snapshot_hash='+ledger['ledger']['snapshot_hash']).data
            self.assertEqual(_sha(exports[kind]),ledger['exports'][kind]['sha256'])
        return dict(data=data,identity=identity,payment=payment,carry=carry,ledger=ledger,exports=exports,query=query)

    def test_actual_private_http_yearly_export_fresh_roles_and_sql_immutability(self):
        value=self.workflow();data=value['data'];employee_id=data['hr']['employee']['id']
        self.assertEqual(self.call('GET','/business/payroll/ledger'+value['query'],token=data['hr']['token']).json,value['ledger'])
        self.call('GET','/business/payroll/ledger/pdf'+value['query']+'&snapshot_hash='+value['ledger']['ledger']['snapshot_hash'],token=data['hr']['token'],status=403)
        self.call('POST','/business/payroll/account-records',request(employee_id=employee_id,kind='identity',revision=0,
            source_file_id=data['hr']['file']['id'],confirmed=True,details=value['identity']['details']),token=data['hr']['token'],status=403)
        self.call('GET','/business/payroll/account-records?employee_id='+employee_id,{'ignored':True},status=400)
        for table in protected_tables():
            column=self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
        self.reopen()
        self.assertEqual(self.call('GET','/business/payroll/ledger'+value['query']).json,value['ledger'])
        self.assertTrue(validate_integrity(self.office))
        business_schema.validate_integrity(self.office)

    def test_real_backup_restore_preserves_ledger_identity_payment_and_prior_months(self):
        value=self.workflow();actor=self.office.user(self.token);runtime=self.office.db.dsn
        before=release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='payroll-account-restore-') as directory:
                saved=backup(fixture.DSN,directory)
                self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_dsn=make_conninfo(runtime,dbname='smartplan_release_check')
            verifier=PostgresOffice(restored_dsn,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            restored=PostgresOffice(restored_dsn)
            try:
                api=Payroll(restored);employee_id=value['data']['hr']['employee']['id']
                self.assertEqual(api.ledger(actor,dict(employee_id=employee_id,year='2026')),value['ledger'])
                for kind in ('pdf','csv','json'):
                    self.assertEqual(api.export_ledger(actor,dict(employee_id=employee_id,year='2026',
                        snapshot_hash=value['ledger']['ledger']['snapshot_hash']),kind)[0],value['exports'][kind])
                self.assertTrue(validate_integrity(restored));business_schema.validate_integrity(restored)
                after=release.snapshot_fingerprint(target)
                for table in protected_tables():self.assertEqual(after[table],before[table])
            finally:restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')


if __name__=='__main__':unittest.main()
