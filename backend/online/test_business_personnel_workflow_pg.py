"""Real MFA/HTTP/private HR archive, runtime ACLs and PostgreSQL backup/restore.

Uses only the existing guarded, disposable loopback database fixture. No tax,
social reporting, bank, payroll provider or external delivery is performed.
"""
import base64
import tempfile
import unittest

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from business_personnel_workflow import PersonnelWorkflow, protected_tables, validate_integrity
from online import release, test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate

fixture = journey.fixture
request = fixture.request


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class PersonnelWorkflowPostgres(unittest.TestCase):
    setUp = journey.CustomerExecutionJourneyPostgres.setUp
    reopen = journey.CustomerExecutionJourneyPostgres.reopen
    login = journey.CustomerExecutionJourneyPostgres.login
    call = journey.CustomerExecutionJourneyPostgres.call

    def workflow(self):
        technician = self.call('POST','/users',dict(email='personnel-tech@example.test',
            password='Synthetic-personnel-password-123',role='technician'),status=201).json['id']
        token = self.login('personnel-tech@example.test','Synthetic-personnel-password-123')
        employee = self.call('POST','/business/employees',request(user_id=technician,
            name='Synthetic payroll employee',weekly_minutes=600,hourly_cost_minor=9999),status=201).json
        original = b'%PDF-1.4\nSynthetic wage agreement\n%%EOF'
        file = self.call('POST','/business/personnel/files',request(employee_id=employee['id'],purpose='personnel',
            owner_visible=False,filename='synthetic-agreement.pdf',media_type='application/pdf',
            content_base64=base64.b64encode(original).decode())).json
        agreement = self.call('POST','/business/personnel/agreements',request(employee_id=employee['id'],revision=0,
            effective_from=self.today[:7]+'-01',employment_kind='minijob',pay_basis='monthly',amount_minor=60300,
            currency='EUR',reference_file_id=file['id'],notes='Explicit synthetic agreement')).json
        receipt = self.call('POST','/business/personnel/files',request(employee_id=employee['id'],purpose='expense_receipt',
            owner_visible=True,filename='synthetic-expense.pdf',media_type='application/pdf',
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic actual travel expense\n%%EOF').decode()),token=token).json
        expense = self.call('POST','/business/personnel/expenses',request(employee_id=employee['id'],revision=0,
            purpose='Synthetic customer visit',start_date=self.today,end_date=self.today,items=[dict(date=self.today,
            description='Actual ticket',amount_minor=1999,currency='EUR',receipt_file_id=receipt['id'])]),token=token).json
        expense = self.call('POST','/business/personnel/expenses/'+expense['id']+'/submit',request(revision=expense['revision']),token=token).json
        expense = self.call('POST','/business/personnel/expenses/'+expense['id']+'/approve',request(revision=expense['revision'],reason='Original checked')).json
        expense = self.call('POST','/business/personnel/expenses/'+expense['id']+'/reimburse',request(revision=expense['revision'],
            amount_minor=1999,confirmed=True,paid_on=self.today,payment_reference='SYN-HR-BANK-001')).json
        preview = self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee['id']+'&month='+self.today[:7]).json
        command = request(employee_id=employee['id'],month=self.today[:7],source_hash=preview['source_hash'],revision=0,completeness_confirmed=True)
        closed = self.call('POST','/business/personnel/payroll-preparations',command).json
        pdf = self.call('GET','/business/personnel/payroll-preparations/'+closed['id']+'/pdf').data
        self.assertEqual(self.call('POST','/business/personnel/payroll-preparations',command).json,closed)
        self.assertFalse(closed['payroll_calculated'])
        self.assertEqual(closed['snapshot']['agreements'][0]['amount_minor'],60300)
        self.assertNotIn('hourly_cost_minor',str(closed))
        return dict(employee=employee,token=token,file=file,original=original,agreement=agreement,
                    expense=expense,closed=closed,command=command,pdf=pdf)

    def test_authenticated_complete_workflow_survives_restart_and_denies_broad_roles_and_destructive_sql(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        data = self.workflow()
        file_path = '/business/personnel/files/'+data['file']['id']+'/content'
        self.call('GET',file_path,token=data['token'],status=403)
        self.assertEqual(self.call('GET',file_path).data,data['original'])
        account = self.call('POST','/users',dict(email='personnel-finance@example.test',
            password='Synthetic-finance-password-123',role='accountant'),status=201).json
        finance_token = self.login('personnel-finance@example.test','Synthetic-finance-password-123')
        self.call('GET','/business/personnel/agreements?employee_id='+data['employee']['id'],token=finance_token,status=403)
        self.call('GET','/business/personnel/payroll-preparations/'+data['closed']['id']+'/pdf',token=finance_token,status=403)
        self.call('GET','/business/personnel/agreements?employee_id='+data['employee']['id'],{'ignored':True},status=400)
        self.call('POST','/business/personnel/payroll-preparations?ignored=1',data['command'],status=400)
        device = self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET',file_path,token=device,status=403)
        self.reopen()
        self.assertEqual(self.call('POST','/business/personnel/payroll-preparations',data['command']).json,data['closed'])
        self.assertEqual(self.call('GET','/business/personnel/payroll-preparations/'+data['closed']['id']+'/pdf').data,data['pdf'])
        for table in protected_tables():
            self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
            column = self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.subTest(table=table,statement=statement),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:
                        self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as migrator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.subTest(table=table,guard=statement),self.assertRaisesRegex(psycopg.Error,'immutable personnel evidence'):
                        with migrator.transaction():
                            migrator.execute('SET LOCAL ROLE "smartplan-migrator"')
                            migrator.execute(statement)
        self.assertTrue(validate_integrity(self.office))
        business_schema.validate_integrity(self.office)

    def test_real_backup_restore_preserves_originals_monthly_pdf_and_receipts(self):
        data = self.workflow()
        actor = self.office.user(self.token)
        runtime = self.office.db.dsn
        before = release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
        target = make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='personnel-pg-restore-') as directory:
                saved = backup(fixture.DSN,directory)
                self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            restored_runtime = make_conninfo(runtime,dbname='smartplan_release_check')
            verifier = PostgresOffice(restored_runtime,allow_restore_pending=True)
            try:
                self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:
                verifier.db.close()
            restored = PostgresOffice(restored_runtime)
            try:
                api = PersonnelWorkflow(restored)
                self.assertEqual(api.file_content(actor,data['file']['id'])[0],data['original'])
                self.assertEqual(api.export(actor,data['closed']['id'],'pdf')[0],data['pdf'])
                self.assertEqual(api.get(actor,'preparation',data['closed']['id']),data['closed'])
                business_schema.validate_integrity(restored)
                after = release.snapshot_fingerprint(target)
                for table in protected_tables():
                    self.assertEqual(after[table],before[table],table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),before)
            finally:
                restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


if __name__ == '__main__':
    unittest.main()
