"""Actual source3 MFA, concurrent writers, immutable tax evidence and restore."""
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
import unittest

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from business_foundation import BusinessFoundation
from business_payroll import Payroll
from business_payroll_calculation_cases import CALCULATION_RULE_VERSION,POLICY_RULE_VERSION,PayrollCalculationCases
from business_payroll_facts import reference
from business_personnel_workflow import PersonnelWorkflow
from business_travel_allowances import TravelAllowances
from online import release,test_business_payroll_entitlements_pg as entitlement_pg
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice
from payroll_travel_recording import validate_tax_recording,TABLES
import test_business_travel_allowances as travel_fixture
from test_payroll_de_2026 import profile

fixture=entitlement_pg.fixture
journey=entitlement_pg.journey
req=fixture.request


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class CalculationPayrollPostgres(unittest.TestCase):
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call
    sources=entitlement_pg.PayrollEntitlementsPostgres.sources

    def setUp(self):
        journey.CustomerExecutionJourneyPostgres.setUp(self)
        self.owner=self.office.user(self.token)

    def workflow(self):
        data=self.sources();employee=data['employee']
        data['agreement']=self.call('POST','/business/personnel/agreements',req(employee_id=employee['id'],
            id=data['agreement']['id'],revision=1,effective_from='2026-01-01',employment_kind='regular',pay_basis='monthly',
            amount_minor=500000,currency='EUR',reference_file_id=data['file']['id'],correction_reason='Actual evidenced regular salary')).json
        data['profile']=self.call('POST','/business/payroll/profiles',req(employee_id=employee['id'],id=data['profile']['id'],revision=1,
            profile=profile('regular',regular_annual_gross_minor=6000000,health_additional_percent='2.90',
                tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0),source_file_id=data['file']['id'],confirmed=True,
            correction_reason='Actual regular tax and insurance evidence')).json
        current=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee['id']+'&month=2026-10').json
        data['preparation']=self.call('POST','/business/personnel/payroll-preparations',req(employee_id=employee['id'],month='2026-10',
            id=data['preparation']['id'],revision=1,source_hash=current['source_hash'],completeness_confirmed=True,
            correction_reason='Actual corrected regular contract')).json
        data['identity']=self.call('POST','/business/payroll/account-records',req(employee_id=employee['id'],kind='identity',revision=0,
            source_file_id=data['file']['id'],confirmed=True,details=entitlement_pg.accounts.PayrollAccountTests.identity_details(self,data,
                employment_from='2026-10-15',employment_to=None))).json
        common=dict(employee_id=employee['id'],employee_revision=employee['revision'],source_file_ids=[data['file']['id']])
        terms=self.call('POST','/business/payroll/facts',req(**common,kind='employment_terms',revision=0,status='active',confirmed=True,
            details=dict(employment_from='2026-10-15',employment_to=None,agreement_refs=[reference(data['agreement'])],
                proration_method='calendar_days_actual',reason='Original actual employment contract'))).json
        details=dict(month='2026-10',preparation_ref=reference(data['preparation']),employment_terms_ref=reference(terms),
            work_schedule_ref=None,profile_refs=[reference(data['profile'])],identity_refs=[reference(data['identity'])],
            tax_treatment='domestic_running_wages',entitlement_decisions=[],verification_note='Actual original period evidence')
        preview=self.call('POST','/business/payroll/periods/preview',dict(common,details=details)).json
        period=self.call('POST','/business/payroll/facts',req(**common,kind='period_case',revision=0,status='active',confirmed=True,
            details=details,preview_hash=preview['preview_hash'])).json
        travel=travel_fixture.TravelWorkflowTests('runTest')
        travel.office=self.office;travel.owner=self.owner;travel.technician=self.office.user(data['tech'])
        travel.employee=employee;travel.project=None;travel.now=self.now
        travel.hr=PersonnelWorkflow(self.office);travel.api=TravelAllowances(self.office)
        travel.file=travel.upload(purpose='expense_receipt',visible=True,actor=travel.technician)
        travel.home=travel.save_site('home');travel.place=travel.save_site('external_fixed')
        trip=travel.api.save_trip(travel.technician,travel.trip_body(requested_meal_minor=1800,tax_choice='flat_25'))['result']
        trip=travel.api.trip_action(travel.technician,trip['id'],'submit',req(employee_id=employee['id'],revision=trip['revision'],
            source_hash=travel.api._basis(employee['id']),confirmed=True))['result']
        settlement=travel.api.approve(self.owner,travel.approval(trip,requested_meal_minor=1800,tax_choice='flat_25',payroll_month='2026-10'))['result']
        policy_input=dict(employee_id=None,employee_revision=None,kind='travel_tax_policy',rule_version=POLICY_RULE_VERSION,
            source_contract_version=1,source_file_ids=[data['file']['id']],details=dict(filing_period_from='2026-10-01',filing_period_to='2026-12-31',
                federal_state='BW',church_method='simplified',church_rate_region='standard',church_method_applies_to_all=True,
                employer_bears_tax=True,verification_note='Actual employer-wide period decision'))
        preview=self.call('POST','/business/payroll/travel-tax-policies/preview',policy_input).json
        policy_command=req(**policy_input,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        policy=self.call('POST','/business/payroll/travel-tax-policies',policy_command).json
        details=dict(month='2026-10',period_case_ref=reference(period),employment_terms_refs=[reference(terms)],
            profile_refs=[reference(data['profile'])],identity_refs=[reference(data['identity'])],segment_events=[],thirty_day_rule=None,
            entitlement_case_refs=[],travel_settlement_refs=[reference(settlement)],verification_note='Actual composite source review',
            flat_tax_decision=dict(policy_ref=reference(policy),church_membership_evidence=None,employee_deduction_file_ref=None,
                tax_certificate_file_ref=None,tax_certificate_issued_on=None,record_on_finalize=True))
        input_=dict(common,kind='calculation_case',rule_version=CALCULATION_RULE_VERSION,source_contract_version=1,details=details)
        preview=self.call('POST','/business/payroll/calculation-cases/preview',input_).json
        self.assertTrue(preview['can_calculate'],preview['plan']['blockers'])
        case_command=req(**input_,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        case=self.call('POST','/business/payroll/calculation-cases',case_command).json
        run_input=dict(employee_id=employee['id'],source_schema_version=3,calculation_case_ref=reference(case))
        preview=self.call('POST','/business/payroll/preview',run_input).json
        command=req(**run_input,preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'],revision=0,confirmed=True)
        return data|dict(case=case,case_command=case_command,policy=policy,policy_command=policy_command,command=command,settlement=settlement)

    def test_actual_mfa_two_writers_fresh_rights_offline_acl_and_restart(self):
        data=self.workflow();barrier=threading.Barrier(2)
        self.assertEqual(0,self.office.db.execute('SELECT COUNT(*) FROM business_payroll_travel_tax_recordings').fetchone()[0])
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return Payroll(office).finalize(self.owner,data['command'])
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,range(2)))
        run=results[0];self.assertEqual(results[0],results[1]);proof=validate_tax_recording(self.office,run)
        self.assertEqual(109,proof['statutory_employer_due_minor'])
        self.assertEqual(1,self.office.db.execute('SELECT COUNT(*) FROM business_payroll_travel_tax_recordings').fetchone()[0])
        self.assertEqual(run,self.call('POST','/business/payroll/runs',data['command']).json)
        self.call('POST','/business/payroll/runs',data['command']|req(),status=409)
        sources=self.call('GET','/business/payroll/travel-tax-policies/sources').json
        self.assertIsNone(sources['employee_id']);self.assertIn(data['file']['id'],[v['id'] for v in sources['files']])
        case_path='/business/payroll/calculation-cases/'+data['case']['id']
        for path in (case_path,'/business/payroll/travel-tax-policies/sources','/business/payroll/runs/'+run['id']):
            self.call('GET',path,token=data['tech'],status=403)
        offline=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('POST','/business/payroll/runs',data['command'],token=offline,status=403)
        self.call('POST','/business/payroll/calculation-cases?ignored=1',data['case_command'],status=400)
        self.call('GET',case_path,{},status=400)
        uid=self.call('POST','/users',dict(email='v5-pg-reviewer@example.test',password='Synthetic-v5-reviewer-123',role='accountant'),status=201).json['id']
        token=self.login('v5-pg-reviewer@example.test','Synthetic-v5-reviewer-123');grants=BusinessFoundation(self.office)
        for name in ('personnel.read','personnel.approve'):
            grants.save_grant(self.owner,req(user_id=uid,permission=name,scope='*',effect='allow',revision=0))
        correction=data['case_command']|req(id=data['case']['id'],revision=1,correction_reason='Independent actual original review')
        second=self.call('POST','/business/payroll/calculation-cases',correction,token=token).json
        grants.save_grant(self.owner,req(user_id=uid,permission='personnel.approve',scope='*',effect='deny',revision=1))
        self.call('POST','/business/payroll/calculation-cases',correction,token=token,status=403)
        grants.save_grant(self.owner,req(user_id=uid,permission='personnel.read',scope='*',effect='deny',revision=1))
        self.call('GET',case_path,token=token,status=403)
        self.reopen();self.assertEqual(run,self.call('GET','/business/payroll/runs/'+run['id']).json)
        self.assertEqual([data['case'],second],self.call('GET',case_path+'/history').json['items'])
        self.assertEqual(proof,validate_tax_recording(self.office,run))
        self.assertEqual(data['case'],self.call('POST','/business/payroll/calculation-cases',data['case_command']).json)
        for table in TABLES:
            for statement in ('UPDATE '+table+' SET run_revision=run_revision','DELETE FROM '+table,'TRUNCATE '+table):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:
                for statement in ('UPDATE '+table+' SET run_revision=run_revision','DELETE FROM '+table):
                    with self.assertRaisesRegex(psycopg.Error,'immutable payroll tax recording'):
                        with operator.transaction():operator.execute('SET LOCAL ROLE "smartplan-migrator"');operator.execute(statement)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_dump_restore_preserves_run_original_case_receipts_pdf_and_tax_without_cash(self):
        data=self.workflow();run=self.call('POST','/business/payroll/runs',data['command']).json
        proof=validate_tax_recording(self.office,run)
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        self.assertEqual(0,self.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        self.office.db.close();target=make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as operator:
            if operator.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            operator.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-payroll-v5-backup-') as directory:
                archive=backup(fixture.DSN,directory);restored=restore(archive,fixture.DSN,target,privileged_operator=True,test_mode=True)
                self.assertTrue(restored['restore_pending'])
            runtime=make_conninfo(self.runtime,dbname='smartplan_release_check');verifier=PostgresOffice(runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            restored_office=PostgresOffice(runtime)
            try:
                api=Payroll(restored_office);cases=PayrollCalculationCases(restored_office)
                self.assertEqual(run,api.finalize(self.owner,data['command']))
                self.assertEqual(data['case'],cases.save(self.owner,data['case_command']))
                self.assertEqual(data['policy'],cases.save(self.owner,data['policy_command']))
                self.assertEqual(pdf,api.export(self.owner,run['id'],'pdf')[0])
                self.assertEqual(proof,validate_tax_recording(restored_office,run))
                self.assertEqual(data['original'],bytes(api.hr._file(data['file']['id'])['original']))
                self.assertTrue(business_schema.validate_integrity(restored_office))
            finally:restored_office.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:operator.execute('DROP DATABASE smartplan_release_check WITH (FORCE)')
        self.reopen()


if __name__=='__main__':unittest.main()
