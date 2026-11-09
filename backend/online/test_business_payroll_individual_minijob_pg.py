"""Actual v11 MFA/HTTP, PostgreSQL concurrency, private originals and restore."""
import base64
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

import business_schema
from business_foundation import BusinessFoundation
from business_payroll import Payroll
from business_payroll_calculation_cases import PayrollCalculationCases
from business_payroll_facts import reference
from core import Problem
from online import test_business_payroll_periods_pg as periods
from online.store import PostgresOffice
from payroll_individual_minijob_2026 import RULE_VERSION, SOURCE_CONTRACT_VERSION, SCOPE, BOOL_FIELDS
from test_payroll_de_2026 import profile
import test_business_payroll_accounts as accounts

fixture=periods.fixture
req=fixture.request


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class IndividualMinijobPostgres(unittest.TestCase):
    setUp=periods.PeriodPayrollPostgres.setUp
    reopen=periods.PeriodPayrollPostgres.reopen
    login=periods.PeriodPayrollPostgres.login
    call=periods.PeriodPayrollPostgres.call
    profile=periods.PeriodPayrollPostgres.profile
    post=periods.PeriodPayrollPostgres.post
    body=periods.PeriodPayrollPostgres.body
    payload=periods.PeriodPayrollPostgres.payload

    def workflow(self,*_,stop_before_upgrade=False,**__):
        uid=self.call('POST','/users',dict(email='individual-minijob@example.test',
            password='Synthetic-minijob-only-123',role='technician'),status=201).json['id']
        tech=self.login('individual-minijob@example.test','Synthetic-minijob-only-123')
        employee=self.call('POST','/business/employees',req(user_id=uid,name='Synthetic individual minijob',
            weekly_minutes=240,hourly_cost_minor=9999,employment_from='2026-10-01',employment_to='2026-10-31'),status=201).json
        self.employee=employee;eid=employee['id'];files={}
        for role in ('wage','health','pension','employment','income','elstam'):
            files[role]=self.call('POST','/business/personnel/files',req(employee_id=eid,purpose='personnel',
                owner_visible=False,filename=role+'-evidenced.pdf',media_type='application/pdf',
                content_base64=base64.b64encode(('%PDF-1.4\nSynthetic '+role+' original\n%%EOF').encode()).decode())).json
        original=files['wage']
        agreement=self.call('POST','/business/personnel/agreements',req(employee_id=eid,revision=0,effective_from='2026-01-01',
            employment_kind='minijob',pay_basis='monthly',amount_minor=50000,currency='EUR',reference_file_id=original['id'])).json
        selected=self.call('POST','/business/payroll/profiles',req(employee_id=eid,revision=0,
            profile=profile('minijob',regular_annual_gross_minor=600000,minijob_tax='individual',health_insurance='statutory_other',tax_class=5),
            source_file_id=original['id'],confirmed=True)).json
        current=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+eid+'&month=2026-10').json
        prepared=self.call('POST','/business/personnel/payroll-preparations',req(employee_id=eid,month='2026-10',revision=0,
            source_hash=current['source_hash'],completeness_confirmed=True)).json
        identity=self.call('POST','/business/payroll/account-records',req(employee_id=eid,kind='identity',revision=0,
            source_file_id=files['elstam']['id'],confirmed=True,details=accounts.PayrollAccountTests.identity_details(self,
                dict(profile=selected),identity_source_schema_version=2,tax_source='elstam_imported'))).json
        common=dict(employee_id=eid,employee_revision=employee['revision'],revision=0,status='active',
                    source_file_ids=[original['id']],confirmed=True)
        terms=self.call('POST','/business/payroll/facts',req(**common,kind='employment_terms',details=dict(
            employment_from='2026-10-01',employment_to='2026-10-31',agreement_refs=[reference(agreement)],
            proration_method='calendar_days_actual',reason='Actual full month minijob'))).json
        details=dict(month='2026-10',preparation_ref=reference(prepared),employment_terms_ref=reference(terms),work_schedule_ref=None,
            profile_refs=[reference(selected)],identity_refs=[reference(identity)],tax_treatment='domestic_running_wages',
            entitlement_decisions=[],verification_note='Actual unchanged full period')
        period_input=dict(employee_id=eid,employee_revision=employee['revision'],details=details,source_file_ids=[original['id']])
        period_preview=self.call('POST','/business/payroll/periods/preview',period_input).json
        self.assertFalse(period_preview['can_calculate'])
        self.assertIn('minijob_individual_tax',[item['code'] for item in period_preview['plan']['blockers']])
        period=self.call('POST','/business/payroll/facts',req(**common,kind='period_case',details=details,preview_hash=period_preview['preview_hash'])).json
        assessment=dict(schema_version=1,employee_id=eid,valid_from='2026-10-01',valid_to='2026-10-31',declaration_date=self.today,
            actual_health_insurance='statutory_family',pension_status='compulsory',**{key:True for key in BOOL_FIELDS},
            **{role+'_evidence_ref':dict(id=value['id'],revision=1,content_hash=value['content_hash'])
               for role,value in files.items() if role!='wage'},verification_note='Actual employee, originals and income reviewed')
        case_input=dict(employee_id=eid,employee_revision=employee['revision'],kind='calculation_case',rule_version=RULE_VERSION,
            source_contract_version=SOURCE_CONTRACT_VERSION,source_file_ids=[value['id'] for value in files.values() if value!=original],
            details=dict(month='2026-10',period_case_ref=reference(period),employment_terms_refs=[reference(terms)],
                profile_refs=[reference(selected)],identity_refs=[reference(identity)],segment_events=[],thirty_day_rule=None,
                entitlement_case_refs=[],travel_settlement_refs=[],flat_tax_decision=None,
                verification_note='Bound individual minijob source case',individual_minijob_assessment=assessment))
        case_preview=self.call('POST','/business/payroll/calculation-cases/preview',case_input).json
        self.assertTrue(case_preview['can_calculate'],case_preview['plan']['blockers'])
        case_command=req(**case_input,revision=0,status='active',confirmed=True,preview_hash=case_preview['preview_hash'])
        if stop_before_upgrade:
            legacy_input=deepcopy(case_input)
            del legacy_input['details']['individual_minijob_assessment']
            legacy_input.update(rule_version='de_2026_segments_entitlements_v5',source_contract_version=1)
            legacy_preview=self.call('POST','/business/payroll/calculation-cases/preview',legacy_input).json
            self.assertFalse(legacy_preview['can_calculate'])
            legacy_command=req(**legacy_input,revision=0,status='active',confirmed=True,preview_hash=legacy_preview['preview_hash'])
            legacy=self.call('POST','/business/payroll/calculation-cases',legacy_command).json
            case_command.update(id=legacy['id'],revision=legacy['revision'],
                correction_reason='Explicit original-backed unsupported minijob correction')
            return dict(employee=employee,legacy=legacy,legacy_command=legacy_command,case_command=case_command)
        case=self.call('POST','/business/payroll/calculation-cases',case_command).json
        inputs=dict(source_schema_version=3,employee_id=eid,calculation_case_ref=reference(case))
        preview=self.call('POST','/business/payroll/preview',inputs).json
        self.assertTrue(preview['can_finalize']);self.assertEqual(preview['calculation']['individual_wage_tax_minor'],4866)
        command=req(**inputs,confirmed=True,revision=0,accepted_scope=SCOPE,preview_hash=preview['preview_hash'])
        run=self.call('POST','/business/payroll/runs',command).json
        self.assertEqual(run['calculation']['net_minor'],43334)
        return dict(employee=employee,file=original,files=files,agreement=agreement,profile=selected,preparation=prepared,
            identity=identity,tech=tech,period=period,case=case,case_command=case_command,inputs=inputs,command=command,run=run)

    def test_actual_mfa_private_scope_fresh_denial_and_restart(self):
        data=self.workflow();run=data['run'];case=data['case']
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        self.call('GET','/business/payroll/calculation-cases/'+case['id'],token=data['tech'],status=403)
        self.call('GET','/business/personnel/files/'+data['files']['health']['id']+'/content',token=data['tech'],status=403)
        self.call('POST','/business/payroll/calculation-cases/preview',dict(data['case_command'],source_contract_version=2),status=400)
        invalid={key:deepcopy(value) for key,value in data['case_command'].items()
                 if key in ('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        invalid['details']['individual_minijob_assessment']['verification_note']='Invalid surrogate \ud800'
        self.call('POST','/business/payroll/calculation-cases/preview',invalid,status=400)
        for invalid_details in (None,1,True,[], 'not structured'):
            self.call('POST','/business/payroll/account-records',req(employee_id=data['employee']['id'],
                kind='identity',revision=0,source_file_id=data['files']['elstam']['id'],
                confirmed=True,details=invalid_details),status=400)
        statement=self.call('GET','/business/payroll/employee-statements/'+run['id'],token=data['tech']).json['statement']
        self.assertEqual(statement['calculation']['individual_wage_tax_minor'],4866)
        self.assertNotIn('individual_minijob_assessment',str(statement))
        uid=self.call('POST','/users',dict(email='individual-reviewer@example.test',password='Synthetic-review-only-123',role='accountant'),status=201).json['id']
        reviewer=self.login('individual-reviewer@example.test','Synthetic-review-only-123')
        grants=BusinessFoundation(self.office)
        for permission in ('personnel.read','personnel.approve'):
            grants.save_grant(self.owner,req(user_id=uid,permission=permission,scope='*',effect='allow',revision=0))
        correction=dict(data['command'],request_id=req()['request_id'],id=run['id'],revision=1,correction_reason='Independent repeated source review')
        self.call('POST','/business/payroll/runs',correction,token=reviewer)
        grants.save_grant(self.owner,req(user_id=uid,permission='personnel.approve',scope='*',effect='deny',revision=1))
        self.call('POST','/business/payroll/runs',correction,token=reviewer,status=403)
        self.reopen()
        self.assertEqual(self.call('POST','/business/payroll/runs',data['command']).json,run)
        self.assertEqual(self.call('POST','/business/payroll/calculation-cases',data['case_command']).json,case)
        self.assertEqual(self.call('GET','/business/payroll/runs/'+run['id']+'/pdf?revision=1').data,pdf)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_concurrent_postgres_v11_writers_accept_one_original(self):
        data=self.workflow();barrier=threading.Barrier(2)
        command=dict(data['command'],request_id=req()['request_id'],id=data['run']['id'],revision=1,correction_reason='Concurrent exact v11 review')
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return Payroll(office).finalize(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(writer,range(2)))
        self.assertEqual(outcomes[0],outcomes[1]);self.assertEqual(outcomes[0]['revision'],2)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_payroll_events WHERE kind='run'").fetchone()[0],2)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_v11_cash_euer_and_frozen_dump_restore(self):
        periods.PeriodPayrollPostgres.test_actual_partial_midijob_payment_euer_and_frozen_dump_restore(self)

    def test_concurrent_explicit_legacy_upgrades_accept_one_preserve_both_originals(self):
        data=self.workflow(stop_before_upgrade=True);barrier=threading.Barrier(2)
        commands=[dict(data['case_command'],request_id=req()['request_id']) for _ in range(2)]
        def writer(command):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                try:return PayrollCalculationCases(office).save(self.owner,command)
                except Problem as error:return error
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(writer,commands))
        accepted=[value for value in outcomes if isinstance(value,dict)]
        rejected=[value for value in outcomes if isinstance(value,Problem)]
        self.assertEqual(len(accepted),1);self.assertEqual(len(rejected),1)
        self.assertEqual(rejected[0].status,409);self.assertEqual(accepted[0]['revision'],2)
        original=self.call('POST','/business/payroll/calculation-cases',data['legacy_command']).json
        self.assertEqual(original,data['legacy'])
        history=self.call('GET','/business/payroll/calculation-cases/'+original['id']+'/history').json['items']
        self.assertEqual(history,[original,accepted[0]])
        self.assertFalse(history[0]['plan']['can_calculate']);self.assertTrue(history[1]['plan']['can_calculate'])
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__=='__main__':unittest.main()
