"""Real PostgreSQL/MFA/HTTP payroll calculation, correction and restore proof.

Synthetic local employees only. No BMF, insurer, bank or reporting transmission.
"""
import tempfile
import unittest

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from business_payroll import Payroll, protected_tables, validate_integrity
from business_personnel_workflow import _sha
from online import release, test_business_personnel_workflow_pg as personnel
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate
from test_payroll_de_2026 import profile

fixture = personnel.fixture
request = personnel.request


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class PayrollPostgres(unittest.TestCase):
    setUp = personnel.PersonnelWorkflowPostgres.setUp
    reopen = personnel.PersonnelWorkflowPostgres.reopen
    login = personnel.PersonnelWorkflowPostgres.login
    call = personnel.PersonnelWorkflowPostgres.call

    def workflow(self):
        data = personnel.PersonnelWorkflowPostgres.workflow(self)
        self.assertEqual(self.today[:4], '2026', 'The versioned fixture requires 2026')
        body = request(employee_id=data['employee']['id'], revision=0,
            profile=profile(effective_from=self.today[:7]+'-01'),
            source_file_id=data['file']['id'], confirmed=True)
        saved = self.call('POST', '/business/payroll/profiles', body).json
        inputs = dict(employee_id=data['employee']['id'], profile_id=saved['id'], profile_revision=saved['revision'],
            preparation_id=data['closed']['id'], preparation_revision=data['closed']['revision'],
            gross_minor=60300, full_month_confirmed=True)
        preview = self.call('POST', '/business/payroll/preview', inputs).json
        self.assertTrue(preview['can_finalize'])
        self.assertEqual(preview['calculation']['net_minor'], 58129)
        command = request(**inputs, preview_hash=preview['preview_hash'], accepted_scope='commercial_minijob_flat_tax',
            confirmed=True, revision=0)
        run = self.call('POST', '/business/payroll/runs', command).json
        self.assertEqual(self.call('POST', '/business/payroll/runs', command).json, run)
        pdf = self.call('GET', '/business/payroll/runs/'+run['id']+'/pdf').data
        self.assertEqual(_sha(pdf), run['pdf_sha256'])
        self.assertEqual(self.call('GET', '/business/payroll/runs/'+run['id']+'/json').json, run)
        return dict(hr=data, profile=saved, profile_command=body, inputs=inputs, run=run, command=command, pdf=pdf)

    def test_real_http_correction_history_fresh_rights_restart_and_append_only_acl(self):
        data = self.workflow()
        rules = self.call('GET', '/business/payroll/rules').json
        self.assertTrue(rules['individual_wage_tax_available'])
        self.assertFalse(rules['official_system_approval'])
        technician = data['hr']['token']
        self.assertEqual(self.call('GET', '/business/payroll/runs/'+data['run']['id'], token=technician).json, data['run'])
        self.call('GET', '/business/payroll/runs/'+data['run']['id']+'/pdf', token=technician, status=403)
        self.call('POST', '/business/payroll/preview', data['inputs'], token=technician, status=403)
        finance = self.call('POST', '/users', dict(email='payroll-pg-finance@example.test',
            password='Synthetic-payroll-finance-password-123', role='accountant'), status=201).json
        finance_token = self.login('payroll-pg-finance@example.test', 'Synthetic-payroll-finance-password-123')
        self.call('GET', '/business/payroll/profiles?employee_id='+data['hr']['employee']['id'], token=finance_token, status=403)
        self.call('GET', '/business/payroll/runs/'+data['run']['id']+'/json', token=finance_token, status=403)
        self.call('GET', '/business/payroll/rules', {'ignored': True}, status=400)
        self.call('POST', '/business/payroll/runs?ignored=1', data['command'], status=400)
        device = self.call('POST', '/business/offline/access', {}, status=201).json['token']
        self.call('GET', '/business/payroll/runs/'+data['run']['id'], token=device, status=403)
        revised = self.call('POST', '/business/payroll/profiles', request(employee_id=data['hr']['employee']['id'],
            id=data['profile']['id'], revision=1, profile={**data['profile']['profile'], 'minijob_rv_exempt': True},
            source_file_id=data['hr']['file']['id'], confirmed=True, correction_reason='Synthetic verified exemption')).json
        self.assertEqual(self.call('POST', '/business/payroll/runs', data['command']).json, data['run'])
        self.call('POST', '/business/payroll/preview', data['inputs'], status=409)
        inputs = {**data['inputs'], 'profile_revision': revised['revision']}
        preview = self.call('POST', '/business/payroll/preview', inputs).json
        command = request(**inputs, preview_hash=preview['preview_hash'], accepted_scope='commercial_minijob_flat_tax',
            confirmed=True, id=data['run']['id'], revision=1, correction_reason='Synthetic corrected exemption')
        updated = self.call('POST', '/business/payroll/runs', command).json
        self.assertEqual(updated['delta']['net_minor'], 2171)
        self.assertEqual(updated['calculation']['net_minor'], 60300)
        self.reopen()
        self.assertEqual(self.call('POST', '/business/payroll/runs', command).json, updated)
        self.assertEqual(self.call('GET', '/business/payroll/runs/'+updated['id']+'/pdf?revision=1').data, data['pdf'])
        self.assertEqual(len(self.call('GET', '/business/payroll/runs/'+updated['id']+'/history').json['items']), 2)
        for table in protected_tables():
            self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
            column = self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for statement in ('UPDATE '+table+' SET '+column+'='+column, 'DELETE FROM '+table, 'TRUNCATE '+table):
                with self.subTest(table=table, statement=statement), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:
                        self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN, autocommit=True) as migrator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column, 'DELETE FROM '+table):
                    with self.subTest(table=table, guard=statement), self.assertRaisesRegex(psycopg.Error, 'immutable payroll record'):
                        with migrator.transaction():
                            migrator.execute('SET LOCAL ROLE "smartplan-migrator"')
                            migrator.execute(statement)
        business_schema.validate_integrity(self.office)

    def test_actual_backup_restore_recalculates_result_and_retains_pdf_sources_receipts(self):
        data = self.workflow()
        actor = self.office.user(self.token)
        runtime = self.office.db.dsn
        before = release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        migrate(fixture.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN), before)
        target = make_conninfo(fixture.DSN, dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN, target, test_mode=True)
        with psycopg.connect(fixture.DSN, autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='payroll-pg-restore-') as directory:
                saved = backup(fixture.DSN, directory)
                self.assertTrue(restore(saved, fixture.DSN, target, privileged_operator=True, test_mode=True)['restore_pending'])
            restored_runtime = make_conninfo(runtime, dbname='smartplan_release_check')
            verifier = PostgresOffice(restored_runtime, allow_restore_pending=True)
            try:
                self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:
                verifier.db.close()
            restored = PostgresOffice(restored_runtime)
            try:
                api = Payroll(restored)
                self.assertEqual(api.export(actor, data['run']['id'], 'pdf')[0], data['pdf'])
                self.assertEqual(api.get(actor, 'run', data['run']['id']), data['run'])
                self.assertEqual(api.finalize(actor, data['command']), data['run'])
                self.assertTrue(validate_integrity(restored))
                business_schema.validate_integrity(restored)
                after = release.snapshot_fingerprint(target)
                for table in protected_tables():
                    self.assertEqual(after[table], before[table], table)
                # Replayed successful command does not mutate the source database.
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN), before)
            finally:
                restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN, autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class RegularPayrollPostgres(unittest.TestCase):
    setUp = personnel.PersonnelWorkflowPostgres.setUp
    reopen = personnel.PersonnelWorkflowPostgres.reopen
    login = personnel.PersonnelWorkflowPostgres.login
    call = personnel.PersonnelWorkflowPostgres.call

    def workflow(self):
        data=personnel.PersonnelWorkflowPostgres.workflow(self)
        employee_id=data['employee']['id']
        agreement=self.call('POST','/business/personnel/agreements',request(employee_id=employee_id,
            id=data['agreement']['id'],revision=1,effective_from=self.today[:7]+'-01',employment_kind='regular',
            pay_basis='monthly',amount_minor=500000,currency='EUR',reference_file_id=data['file']['id'],
            correction_reason='Synthetic regular monthly contract, independent of project cost rate')).json
        hr_preview=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee_id+'&month='+self.today[:7]).json
        preparation=self.call('POST','/business/personnel/payroll-preparations',request(employee_id=employee_id,
            id=data['closed']['id'],month=self.today[:7],source_hash=hr_preview['source_hash'],revision=1,
            completeness_confirmed=True,correction_reason='Synthetic corrected regular contract')).json
        saved=self.call('POST','/business/payroll/profiles',request(employee_id=employee_id,revision=0,
            profile=profile('regular',effective_from=self.today[:7]+'-01',regular_annual_gross_minor=6000000,
                health_additional_percent='2.90',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0),
            source_file_id=data['file']['id'],confirmed=True)).json
        inputs=dict(employee_id=employee_id,profile_id=saved['id'],profile_revision=1,
            preparation_id=preparation['id'],preparation_revision=preparation['revision'],gross_minor=500000,full_month_confirmed=True)
        preview=self.call('POST','/business/payroll/preview',inputs).json
        self.assertEqual(preview['calculation']['net_minor'],313009)
        command=request(**inputs,preview_hash=preview['preview_hash'],accepted_scope='regular_standard_monthly',confirmed=True,revision=0)
        run=self.call('POST','/business/payroll/runs',command).json
        self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        self.assertEqual(_sha(pdf),run['pdf_sha256'])
        return dict(hr=data,profile=saved,inputs=inputs,run=run,command=command,pdf=pdf)

    def test_regular_pap_correction_exports_and_restart(self):
        data=self.workflow()
        saved=self.call('POST','/business/payroll/profiles',request(employee_id=data['hr']['employee']['id'],
            id=data['profile']['id'],revision=1,profile={**data['profile']['profile'],'tax_allowance_monthly_minor':20000},
            source_file_id=data['hr']['file']['id'],confirmed=True,correction_reason='Synthetic reviewed tax allowance')).json
        self.call('POST','/business/payroll/preview',data['inputs'],status=409)
        inputs={**data['inputs'],'profile_revision':saved['revision']}
        preview=self.call('POST','/business/payroll/preview',inputs).json
        corrected=self.call('POST','/business/payroll/runs',request(**inputs,preview_hash=preview['preview_hash'],
            accepted_scope='regular_standard_monthly',confirmed=True,id=data['run']['id'],revision=1,
            correction_reason='Synthetic tax allowance recalculation')).json
        self.assertGreater(corrected['calculation']['net_minor'],313009)
        self.assertEqual(corrected['delta']['net_minor'],-corrected['delta']['employee_tax_minor'])
        self.assertEqual(corrected['delta']['employee_social_total_minor'],0)
        self.reopen()
        self.assertEqual(self.call('POST','/business/payroll/runs',data['command']).json,data['run'])
        self.assertEqual(self.call('GET','/business/payroll/runs/'+data['run']['id']+'/pdf?revision=1').data,data['pdf'])
        self.assertEqual(self.call('GET','/business/payroll/runs/'+data['run']['id']+'/json?revision=1').json,data['run'])
        self.call('POST','/business/payroll/preview',inputs,token=data['hr']['token'],status=403)
        business_schema.validate_integrity(self.office)

    test_actual_backup_restore_recalculates_regular_pap_and_retains_sources = PayrollPostgres.test_actual_backup_restore_recalculates_result_and_retains_pdf_sources_receipts


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class FactorPayrollPostgres(unittest.TestCase):
    setUp = personnel.PersonnelWorkflowPostgres.setUp
    reopen = personnel.PersonnelWorkflowPostgres.reopen
    login = personnel.PersonnelWorkflowPostgres.login
    call = personnel.PersonnelWorkflowPostgres.call

    def workflow(self):
        data=RegularPayrollPostgres.workflow(self)
        original=dict(data)
        employee_id=data['hr']['employee']['id']
        saved=self.call('POST','/business/payroll/profiles',request(employee_id=employee_id,
            id=data['profile']['id'],revision=1,profile={**data['profile']['profile'],
                'tax_class':4,'special_cases':['tax_factor'],'tax_factor':'0.753'},
            source_file_id=data['hr']['file']['id'],confirmed=True,
            correction_reason='Synthetic documented effective class-IV factor')).json
        inputs={**data['inputs'],'profile_revision':saved['revision']}
        preview=self.call('POST','/business/payroll/preview',inputs).json
        self.assertEqual(preview['calculation']['net_minor'],332342)
        command=request(**inputs,preview_hash=preview['preview_hash'],
            accepted_scope='regular_standard_factor_monthly',confirmed=True,
            id=data['run']['id'],revision=1,correction_reason='Synthetic factor recalculation')
        run=self.call('POST','/business/payroll/runs',command).json
        self.assertEqual(run['delta']['employee_tax_minor'],-19333)
        self.assertEqual(run['delta']['net_minor'],19333)
        self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        self.assertEqual(_sha(pdf),run['pdf_sha256'])
        return dict(data,original=original,profile=saved,inputs=inputs,run=run,command=command,pdf=pdf)

    def test_factor_recalculation_and_narrow_employee_statement_survive_restart(self):
        data=self.workflow()
        rules=self.call('GET','/business/payroll/rules').json
        self.assertEqual(rules['regular_factor_rules']['version'],'de_2026_standard_factor_monthly_v8')
        self.reopen()
        self.assertEqual(self.call('POST','/business/payroll/runs',data['command']).json,data['run'])
        self.assertEqual(self.call('POST','/business/payroll/runs',data['original']['command']).json,data['original']['run'])
        self.assertEqual(self.call('GET','/business/payroll/runs/'+data['run']['id']+'/pdf?revision=1').data,data['original']['pdf'])
        result=self.call('GET','/business/payroll/employee-statements/'+data['run']['id'],token=data['hr']['token']).json['statement']
        self.assertEqual(result['calculation']['net_minor'],332342)
        self.assertNotIn('tax_parameters',result['calculation'])
        self.call('POST','/business/payroll/preview',data['inputs'],token=data['hr']['token'],status=403)
        business_schema.validate_integrity(self.office)

    test_actual_backup_restore_recalculates_factor_and_retains_originals = PayrollPostgres.test_actual_backup_restore_recalculates_result_and_retains_pdf_sources_receipts


if __name__ == '__main__':
    unittest.main()
