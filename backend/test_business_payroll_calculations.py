"""Actual v5 cases, atomic tax treatment, accounts and financial ownership."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
import business_schema
import business_payroll_calculation_cases as cases
from business_payroll_facts import reference
from business_personnel_workflow import _sha
from core import Problem,canonical
from payroll_travel_recording import validate_tax_recording
from test_business_payroll import rid
import test_business_payroll_facts as facts_fixture
import test_business_payroll_accounts as accounts_fixture
import test_business_payroll_calculation_cases as case_fixture
import test_business_payroll_periods as periods_fixture


class CalculationPayrollWorkflow(unittest.TestCase):
    details=case_fixture.CalculationCaseTests.details
    request=case_fixture.CalculationCaseTests.request
    policy=case_fixture.CalculationCaseTests.policy
    regular=periods_fixture.PayrollPeriodWorkflowTests.regular

    def setUp(self):
        names=business_schema.MODULE_NAMES
        for name in ('business_payroll_calculation_cases','payroll_travel_recording'):
            if name not in names:names+=(name,)
        registry=patch.object(business_schema,'MODULE_NAMES',names)
        registry.start();self.addCleanup(registry.stop)
        self.f=facts_fixture.PayrollFactTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.regular();self.base,_,_=self.f.period()
        self.api=cases.PayrollCalculationCases(self.f.office,clock=lambda:self.f.now)

    def case(self,details=None,**changes):
        body,_=self.request(details)
        body.update(changes)
        return self.api.save(self.f.owner,body),body

    def command(self,case,**changes):
        data=dict(source_schema_version=3,employee_id=self.f.employee['id'],calculation_case_ref=reference(case))
        return periods_fixture.command(self.f.payroll,self.f.owner,data)|changes

    def travel(self,*,requested=1800,tax_choice='flat_25',meal_price=None,meal_kind='breakfast'):
        from business_travel_allowances import TravelAllowances
        import test_business_travel_allowances as fixture
        f=self.f;t=fixture.TravelWorkflowTests('runTest')
        for key in ('office','employee','owner','technician','project','hr','now'):setattr(t,key,getattr(f,key))
        t.api=TravelAllowances(f.office,clock=lambda:f.now)
        t.file=t.upload(purpose='expense_receipt',visible=True,actor=f.technician)
        t.home=t.save_site('home');t.place=t.save_site('external_fixed')
        meals=[] if meal_price is None else [dict(id=rid(),date='2026-10-26',kind=meal_kind,provider='employer_arranged',
            offered=True,is_meal=True,price_minor=meal_price,employee_paid_minor=0,replacement_for=None,source_file_ids=[t.file['id']])]
        trip=t.api.save_trip(f.technician,t.trip_body(requested_meal_minor=requested,tax_choice=tax_choice,meals=meals))['result']
        trip=t.api.trip_action(f.technician,trip['id'],'submit',dict(request_id=rid(),employee_id=f.employee['id'],revision=trip['revision'],source_hash=t.api._basis(f.employee['id']),confirmed=True))['result']
        settled=t.api.approve(f.owner,t.approval(trip,requested_meal_minor=requested,tax_choice=tax_choice,payroll_month='2026-10'))['result']
        return t,settled

    def travel_case(self,*,shift=False,requested=1800,tax_choice='flat_25',meal_price=None,meal_kind='breakfast'):
        t,settlement=self.travel(requested=requested,tax_choice=tax_choice,meal_price=meal_price,meal_kind=meal_kind)
        details=self.details();details['travel_settlement_refs']=[reference(settlement)]
        policy=body=None
        if settlement['calculation']['totals']['flat_taxable_minor']:
            policy,body=self.policy(employer_bears_tax=not shift)
            details['flat_tax_decision']=dict(policy_ref=reference(policy),church_membership_evidence=None,
                employee_deduction_file_ref=dict(id=self.f.data['file']['id'],revision=1,content_hash=self.f.data['file']['content_hash']) if shift else None,
                tax_certificate_file_ref=None,tax_certificate_issued_on=None,record_on_finalize=True)
        case,_=self.case(details)
        return case,policy,body,t,settlement

    def payment(self,run,**changes):
        f=self.f
        actual=run['calculation']['net_minor']-run['calculation'].get('net_deductions_minor',0)
        data=accounts_fixture.PayrollAccountTests.payment_details(f,run,f.identity,
            payments=[dict(paid_on='2026-10-31',amount_minor=actual,payment_reference='SYN-V5-ACTUAL-NET-001')],**changes)
        return f.save_account(f.data,'payment',data)[0]

    def finance(self):
        from business_accounting import Accounting
        from business_accounting_euer import EuerAccounting
        from business_accounting_profile import AccountingPreparationProfile
        from business_payroll_cash import PayrollCash
        from online.instance import bind
        from online.storage import Storage
        import test_business_payroll_cash as fixture
        f=self.f;c=fixture.PayrollCashTests('runTest');c.f=f;c.office=f.office;c.owner=f.owner;c.clock=lambda:f.now
        c.instance=rid();c.key=Fernet.generate_key()
        c.storage=Storage(c.office,c.key,'payroll-v5.example.test',config={'server':{'path':str(Path(f.temporary.name)/'company')}})
        bind(c.office,c.instance,'payroll-v5.example.test',c.key,c.storage)
        c.api=PayrollCash(c.office,clock=c.clock);c.euer=EuerAccounting(c.office,clock=c.clock)
        c.account=Accounting(c.office,clock=c.clock).create_account(c.owner,dict(request_id=rid(),confirmation=True,code='1200',name='Synthetic v5 company bank',kind='bank'))
        profile=AccountingPreparationProfile(c.office,clock=c.clock);state=profile.state(c.owner)
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic supported EÜR facts',evidence_reference='Synthetic original employer evidence',
            profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from='2026-01-01',bookkeeping_start='2026-01-01'))
        preview=profile.preview(c.owner,body);profile.confirm(c.owner,dict(body,request_id=rid(),confirmation=True,preview_hash=preview['preview_hash']))
        return c

    def test_actual_source3_run_keeps_exact_replay_pdf_and_all_identity_intervals(self):
        f=self.f;case,_=self.case();body=self.command(case);run=f.payroll.finalize(f.owner,body)
        self.assertEqual('regular_standard_segments',run['calculation']['scope'])
        self.assertEqual(274194,run['calculation']['gross_minor'])
        self.assertEqual(run,f.payroll.finalize(f.owner,body))
        self.assertIsNone(validate_tax_recording(f.office,run))
        payment=self.payment(run)
        self.assertEqual(reference(f.identity),reference(payment['sources']['identity_intervals'][0]['identity']))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertTrue(ledger['months'][9]['wage_account']['complete'])
        self.assertEqual(reference(case),ledger['months'][9]['source_refs']['calculation_case'])
        self.assertFalse(ledger['recorded_travel']['letter_m'])
        for format_ in ('pdf','json'):
            content=f.payroll.export(f.owner,run['id'],format_)[0]
            self.assertTrue(content)
        for format_ in ('pdf','csv','json'):
            content=f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),format_)[0]
            self.assertIn(b'de_2026_segments_entitlements_v5',content)
        f.problem(403,lambda:f.payroll.get(f.technician,'run',run['id']))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_tax_treatment_exists_only_after_actual_atomic_finalization_and_once(self):
        f=self.f;case,_,_,_,_=self.travel_case()
        self.assertFalse(case['sources']['flat_travel_tax']['recording_context']['actual_recorded'])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_travel_tax_recordings').fetchone()[0])
        body=self.command(case);run=f.payroll.finalize(f.owner,body);proof=validate_tax_recording(f.office,run)
        self.assertTrue(proof['actual_recorded']);self.assertFalse(proof['actual_payment_created']);self.assertFalse(proof['statutory_transmitted'])
        self.assertEqual((400,100,5,4,109),(proof['amount_minor'],proof['wage_tax_minor'],proof['solidarity_minor'],proof['church_tax_minor'],proof['statutory_employer_due_minor']))
        self.assertEqual(run['created_at'],proof['created_at']);self.assertEqual(reference(run),proof['run_ref'])
        self.assertEqual(run,f.payroll.finalize(f.owner,body))
        self.assertEqual(1,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_travel_tax_recordings').fetchone()[0])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_failed_tax_append_rolls_back_payroll_receipt_and_run(self):
        f=self.f;case,_,_,_,_=self.travel_case();body=self.command(case)
        with patch('payroll_travel_recording.record_tax_treatment',side_effect=Problem(409,'Synthetic atomic tax-record failure')):
            f.problem(409,lambda:f.payroll.finalize(f.owner,body))
        self.assertEqual(0,f.office.db.execute("SELECT COUNT(*) FROM business_payroll_events WHERE kind='run'").fetchone()[0])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_travel_tax_recordings').fetchone()[0])
        self.assertIsNone(f.office.db.execute('SELECT 1 FROM business_payroll_requests WHERE request_id=?',(body['request_id'],)).fetchone())
        run=f.payroll.finalize(f.owner,body);self.assertTrue(validate_tax_recording(f.office,run)['actual_recorded'])

    def test_voiding_policy_cannot_change_method_of_a_period_with_an_effective_tax_record(self):
        f=self.f;case,policy,body,_,_=self.travel_case();run=f.payroll.finalize(f.owner,self.command(case))
        self.api.save(f.owner,body|dict(request_id=rid(),id=policy['id'],revision=1,status='void',correction_reason='Archived policy original'))
        f.problem(409,lambda:self.policy(method='evidence',filing_period_from='2026-11-01',filing_period_to='2026-11-30'))
        self.assertEqual(run,f.payroll.get(f.owner,'run',run['id']))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_corrected_run_invalidates_current_travel_processing_but_preserves_original_tax_record(self):
        from payroll_travel_link import assert_travel_processed,validate_travel_processing
        f=self.f;case,_,_,_,settlement=self.travel_case();command=self.command(case)
        original=f.payroll.finalize(f.owner,command);tax_record=validate_tax_recording(f.office,original)
        source_hash=case['sources']['travel_sources'][0]['source_hash']
        proof=assert_travel_processed(f.office,f.owner,reference(settlement),'2026-10',source_hash)
        corrected,_=self.case(self.details(),id=case['id'],revision=1,correction_reason='Actual travel payroll assignment withdrawn for correction')
        body=self.command(corrected,id=original['id'],revision=1,correction_reason='Actual original payroll calculation corrected')
        current=f.payroll.finalize(f.owner,body)
        f.problem(409,lambda:assert_travel_processed(f.office,f.owner,reference(settlement),'2026-10',source_hash))
        self.assertEqual(tax_record,validate_tax_recording(f.office,original))
        self.assertIsNone(validate_tax_recording(f.office,current))
        self.assertTrue(validate_travel_processing(f.office,proof,reference(settlement),'2026-10',source_hash))
        self.assertEqual(original,f.payroll.finalize(f.owner,command))
        self.assertEqual(1,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_travel_tax_recordings').fetchone()[0])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_date_change_requires_new_case_and_preserves_accepted_old_case(self):
        f=self.f;case,_,_,_,_=self.travel_case();body=self.command(case)
        f.now=f.now.replace(day=4)
        f.problem(409,lambda:f.payroll.finalize(f.owner,body))
        saved,newbody=self.case(case['details'],id=case['id'],revision=1,correction_reason='Actual finalization moved to next day')
        self.assertEqual('2026-11-04',saved['sources']['flat_travel_tax']['recording_context']['planned_recording_on'])
        run=f.payroll.finalize(f.owner,self.command(saved));self.assertEqual('2026-11-04',validate_tax_recording(f.office,run)['recorded_on'])
        self.assertEqual(case,self.api.get(f.owner,case['id'],True)['items'][0])

    def test_actual_net_after_shifted_tax_reaches_cash_euer_without_duplicate_travel_cash(self):
        f=self.f;c=self.finance();case,_,_,travel,settlement=self.travel_case(shift=True)
        run=f.payroll.finalize(f.owner,self.command(case));calc=run['calculation']
        self.assertEqual(109,calc['net_deductions_minor'])
        wrong=accounts_fixture.PayrollAccountTests.payment_details(f,run,f.identity)
        f.problem(400,lambda:f.save_account(f.data,'payment',wrong))
        paid=self.payment(run);net=c.import_cash(c.body(paid));c.post('payroll_cash',c.payload(net))
        remit=c.import_cash(c.remittance(f.data,run,paid));c.post('payroll_cash',c.payload(remit))
        total=c.euer.report(f.owner,2026)['totals']['confirmed_expenses']
        self.assertEqual(str(calc['employer_total_excluding_accident_insurance_minor']//100)+'.'+str(calc['employer_total_excluding_accident_insurance_minor']%100).zfill(2),total)
        from payroll_travel_link import assert_travel_processed
        adapter=case['sources']['travel_sources'][0]
        proof=assert_travel_processed(f.office,f.owner,reference(settlement),'2026-10',adapter['source_hash'])
        self.assertEqual(reference(run),proof['run_ref'])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0])
        from travel_allowance_cash import record_payment,public_source
        travel.instance=c.instance;travel.account=c.account
        command=travel.payment(settlement,1400)
        accepted=record_payment(travel.api,f.owner,command)
        self.assertEqual(accepted,record_payment(travel.api,f.owner,command))
        public=public_source(f.office,accepted['target_id']);self.assertEqual('14.00',public['cash_movements'][0]['amount'])
        c.post('travel_cash',dict(payment_id=accepted['target_id'],revision=1,source_hash=public['source_hash'],accounts={'travel_allowance':'6664'}))
        combined=calc['employer_total_excluding_accident_insurance_minor']+1400
        self.assertEqual(str(combined//100)+'.'+str(combined%100).zfill(2),c.euer.report(f.owner,2026)['totals']['confirmed_expenses'])
        f.problem(409,lambda:record_payment(travel.api,f.owner,travel.payment(settlement,1)))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_non_cash_meal_is_deducted_without_inventing_m(self):
        f=self.f;case,_,_,_,_=self.travel_case(requested=1400,tax_choice='individual',meal_price=6500,meal_kind='lunch')
        run=f.payroll.finalize(f.owner,self.command(case));calc=run['calculation']
        self.assertEqual(6500,calc['net_deductions_minor']);self.assertEqual(6500,calc['period_details']['travel']['benefit_in_kind_non_cash_minor'])
        self.assertFalse(calc['period_details']['travel']['letter_m'])
        paid=self.payment(run)
        self.assertEqual(calc['net_minor']-6500,sum(v['amount_minor'] for v in paid['details']['payments']))
        self.assertIsNone(validate_tax_recording(f.office,run))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_m_only_does_not_increase_cash_or_tax_and_reimbursement_stays_external(self):
        from payroll_calculations_2026 import calculate_calculation_source
        f=self.f;_,preview=self.request();expected=calculate_calculation_source(preview['source_snapshot'],
            rule_version=cases.CALCULATION_RULE_VERSION,source_contract_version=1)
        case,_,_,travel,settlement=self.travel_case(requested=0,tax_choice='tax_free_only',meal_price=1200)
        run=f.payroll.finalize(f.owner,self.command(case));calc=run['calculation']
        self.assertTrue(calc['period_details']['travel']['letter_m'])
        for key in ('gross_minor','net_minor','employee_tax_minor','employee_social_total_minor','employer_total_excluding_accident_insurance_minor'):
            self.assertEqual(expected[key],calc[key])
        self.assertEqual(0,calc['net_deductions_minor']);self.assertIsNone(validate_tax_recording(f.office,run))
        self.payment(run)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertTrue(ledger['recorded_travel']['letter_m'])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_individual_travel_tax_includes_only_the_actual_extra_payment_and_blocks_wrong_inflow_month(self):
        from payroll_calculations_2026 import calculate_calculation_source
        f=self.f;_,preview=self.request();expected=calculate_calculation_source(preview['source_snapshot'],
            rule_version=cases.CALCULATION_RULE_VERSION,source_contract_version=1)
        case,_,_,_,_=self.travel_case(requested=1800,tax_choice='individual')
        run=f.payroll.finalize(f.owner,self.command(case));calc=run['calculation']
        self.assertEqual(400,calc['period_details']['travel']['individual_taxable_payroll_minor'])
        self.assertEqual(expected['gross_minor']+400,calc['gross_minor'])
        self.assertEqual(1400,calc['period_details']['travel']['tax_free_external_minor'])
        wrong=accounts_fixture.PayrollAccountTests.payment_details(f,run,f.identity,
            payments=[dict(paid_on='2026-11-01',amount_minor=calc['net_minor'],payment_reference='SYN-WRONG-INFLOW')])
        f.problem(409,lambda:f.save_account(f.data,'payment',wrong))
        self.payment(run);self.assertIsNone(validate_tax_recording(f.office,run))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_departure_and_reentry_bind_distinct_original_identity_and_employment_intervals(self):
        f=self.f;first_term=self.base['sources']['employment_terms']
        f.employee=f.call(f.planning,'save_employee',f.owner,dict(request_id=rid(),id=f.employee['id'],revision=f.employee['revision'],
            employment_from='2026-10-15',employment_to='2026-10-20'))
        first_term=f.api.save(f.owner,f.body('employment_terms',first_term['details']|dict(employment_to='2026-10-20'),
            id=first_term['id'],revision=1,correction_reason='Actual documented departure'))
        first_identity,_=f.save_account(f.data,'identity',f.identity['details']|dict(employment_to='2026-10-20'),
            id=f.identity['id'],revision=1,correction_reason='Original departure identity evidence')
        first_profile=f.data['profile']
        f.employee=f.call(f.planning,'save_employee',f.owner,dict(request_id=rid(),id=f.employee['id'],revision=f.employee['revision'],
            employment_from='2026-10-25',employment_to='2026-10-31'))
        second_profile=f.payroll.save_profile(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],revision=0,
            profile=first_profile['profile']|dict(effective_from='2026-10-25'),source_file_id=f.data['file']['id'],confirmed=True))
        f.data=f.data|dict(profile=second_profile)
        f.identity,_=f.save_account(f.data,'identity',f.identity_details(f.data,employment_from='2026-10-25',employment_to='2026-10-31',valid_from='2026-10-25'))
        second_term=f.api.save(f.owner,f.body('employment_terms',first_term['details']|dict(employment_from='2026-10-25',employment_to='2026-10-31')))
        preview=f.hr.preview(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        preparation=f.hr.close_preparation(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],month='2026-10',
            id=f.data['preparation']['id'],revision=f.data['preparation']['revision'],source_hash=preview['source_hash'],
            completeness_confirmed=True,correction_reason='Actual departure and reentry sources'))
        f.data=f.data|dict(preparation=preparation)
        details=f.period_details(second_term)
        preview=f.api.preview(f.owner,f.preview_body(details))
        self.base=f.api.save(f.owner,f.body('period_case',details,id=self.base['id'],revision=1,
            preview_hash=preview['preview_hash'],correction_reason='Current actual reentry preparation'))
        f.problem(409,lambda:self.request(self.details()))
        details=self.details()|dict(employment_terms_refs=sorted([reference(first_term),reference(second_term)],key=lambda v:v['id']),
            profile_refs=sorted([reference(first_profile),reference(second_profile)],key=lambda v:v['id']),
            identity_refs=sorted([reference(first_identity),reference(f.identity)],key=lambda v:v['id']))
        case,_=self.case(details);run=f.payroll.finalize(f.owner,self.command(case));calc=run['calculation']
        self.assertEqual(209677,calc['gross_minor'])
        self.assertEqual([6,7],[v['days'] for v in calc['period_details']['social_periods']])
        self.assertEqual([6,7],[v['tax_days'] for v in calc['period_details']['tax_periods']])
        paid=self.payment(run)
        self.assertEqual([reference(first_identity),reference(f.identity)],[reference(v['identity']) for v in paid['sources']['identity_intervals']])
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertTrue(ledger['months'][9]['wage_account']['complete'])
        self.assertTrue(ledger['statutory_wage_account_complete'],ledger['account_completeness_issues'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_changed_recording_is_rejected_by_reads_exports_and_financial_sources(self):
        f=self.f;case,_,_,_,_=self.travel_case();run=f.payroll.finalize(f.owner,self.command(case))
        row=f.office.db.execute('SELECT * FROM business_payroll_travel_tax_recordings').fetchone();payload=json.loads(row['payload_json']);payload['wage_tax_minor']=0
        f.office.db.execute('DROP TRIGGER business_payroll_travel_tax_recordings_update_guard')
        f.office.db.execute('UPDATE business_payroll_travel_tax_recordings SET payload_json=?,content_hash=?',(canonical(payload),_sha(payload)))
        for action in (lambda:f.payroll.get(f.owner,'run',run['id']),lambda:f.payroll.export(f.owner,run['id'],'pdf'),
                       lambda:f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026')),lambda:self.payment(run)):
            f.problem(500,action)
        with self.assertRaises(ValueError):business_schema.validate_integrity(f.office)

    def test_actual_unpaid_fact_changes_payroll_and_records_open_statutory_marker(self):
        from business_payroll_entitlements import PayrollEntitlements
        f=self.f;api=PayrollEntitlements(f.office,clock=lambda:f.now)
        original=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash'])
        details=dict(case_key=rid(),employment_terms_ref=reference(self.base['sources']['employment_terms']),work_schedule_refs=[],
            preparation_refs=[],agreement_refs=[reference(f.data['agreement'])],sickness_history_ref=None,
            input=dict(**{'from':'2026-10-20','to':'2026-10-24'},employment_to=None,employment_continues=True,no_wage_claim=True,
                intervening_paid_days=[],evidence_refs=[original],exceptions=[]),verification_note='Actual five unpaid days')
        proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='unpaid_continuation',details=details,source_file_ids=[original['id']])
        preview=api.preview(f.owner,proposal)
        fact=api.save(f.owner,dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        before=[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')]
        case,_=self.case(self.details()|dict(entitlement_case_refs=[reference(fact)]))
        run=f.payroll.finalize(f.owner,self.command(case));self.assertEqual(193548,run['calculation']['gross_minor'])
        self.assertEqual(17,run['calculation']['period_details']['social_periods'][0]['days'])
        self.payment(run)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertFalse(ledger['statutory_wage_account_complete'])
        self.assertIn('unpaid_statutory_marker_requires_evidence',ledger['account_completeness_issues'])
        self.assertEqual(5,len(ledger['recorded_unpaid_periods'][0]['dates']))
        self.assertEqual(before,[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_v3_travel_original_keeps_explicit_rule_when_bound_to_source3(self):
        f=self.f
        with patch('payroll_travel_2026.RULE_VERSION','de_travel_2026_v3'),patch('business_travel_allowances.RULE_VERSION','de_travel_2026_v3'):
            case,_,_,travel,settlement=self.travel_case()
        self.assertEqual('de_travel_2026_v3',case['sources']['travel_sources'][0]['rule_version'])
        self.assertTrue(settlement['calculation']['ground_calendar_sources'])
        run=f.payroll.finalize(f.owner,self.command(case))
        self.assertEqual(400,run['calculation']['period_details']['travel']['flat_taxable_payroll_minor'])
        self.assertEqual(reference(settlement),run['source']['calculation_case']['sources']['travel_sources'][0]['settlement_ref'])
        self.assertEqual(run,f.payroll.get(f.owner,'run',run['id']))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_v3_sickness_phases_feed_one_monthly_claim_without_overlap_or_fake_hours(self):
        from business_payroll_entitlements import PayrollEntitlements
        from test_business_payroll_entitlements import PayrollEntitlementTests
        f=self.f;f.now=f.now.replace(month=12,day=3)
        schedule=PayrollEntitlementTests.schedule(f,'2026-11')
        original=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash'])
        first=dict(id=rid(),**{'from':'2026-11-14','to':'2026-12-05'},onset='non_workday',first_scheduled_day=None,
            continuation_group=rid(),recovery_before=True,unculpable=True,evidence_refs=[original])
        added=dict(first,id=rid(),**{'from':'2026-11-20','to':'2026-12-31'},onset='during_existing_au',continuation_group=rid(),recovery_before=False)
        source=dict(employment_from='2026-10-15',employment_to=None,pay_basis='monthly',complete_from='2026-10-15',
            complete_through='2026-12-31',history_evidence_refs=[original],episodes=[first,added],
            prevention_cases=[dict(id=rid(),episode_ids=[first['id'],added['id']],evidence_refs=[original])])
        details=dict(case_key=rid(),employment_terms_ref=reference(self.base['sources']['employment_terms']),work_schedule_refs=[],
            preparation_refs=[],agreement_refs=[reference(f.data['agreement'])],sickness_history_ref=None,input=source,
            verification_note='Actual distinct causes in one prevention case')
        api=PayrollEntitlements(f.office,clock=lambda:f.now)
        proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='sickness_history',details=details,source_file_ids=[original['id']])
        preview=api.preview(f.owner,proposal)
        history=api.save(f.owner,dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        self.assertEqual('de_2026_sickness_phases_v3',history['plan']['rule_version'])
        absence=f.call(f.planning,'save_absence',f.technician,dict(request_id=rid(),employee_id=f.employee['id'],
            start_date='2026-11-14',end_date='2026-11-30',kind='sick',details='Protected sick leave original'))
        f.call(f.planning,'approve_absence',f.owner,absence['id'],dict(request_id=rid(),revision=absence['revision'],status='approved'))
        preview=f.hr.preview(f.owner,dict(employee_id=f.employee['id'],month='2026-11'))
        preparation=f.hr.close_preparation(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],month='2026-11',revision=0,
            source_hash=preview['source_hash'],completeness_confirmed=True))
        details=f.period_details(self.base['sources']['employment_terms'],month='2026-11',preparation_ref=reference(preparation),
            work_schedule_ref=reference(schedule))
        preview=f.api.preview(f.owner,f.preview_body(details))
        period=f.api.save(f.owner,f.body('period_case',details,preview_hash=preview['preview_hash']))
        details=self.details()|dict(month='2026-11',period_case_ref=reference(period),entitlement_case_refs=[reference(history)])
        case,_=self.case(details);run=f.payroll.finalize(f.owner,self.command(case))
        self.assertEqual(500000,run['calculation']['gross_minor'])
        self.assertEqual([],run['calculation']['period_details']['unpaid_dates'])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_time_days').fetchone()[0])
        self.assertEqual(reference(history),run['calculation']['period_details']['entitlement_sources'][0]['reference'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_missing_tax_record_blocks_restore_integrity_even_without_payment(self):
        f=self.f;case,_,_,_,_=self.travel_case();run=f.payroll.finalize(f.owner,self.command(case))
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        f.office.db.execute('DROP TRIGGER business_payroll_travel_tax_recordings_delete_guard')
        f.office.db.execute('DELETE FROM business_payroll_travel_tax_recordings')
        f.problem(500,lambda:f.payroll.get(f.owner,'run',run['id']))
        with self.assertRaises(ValueError):business_schema.validate_integrity(f.office)

    def preemployment_zero_case(self):
        from business_payroll_entitlements import PayrollEntitlements
        f=self.f;api=PayrollEntitlements(f.office,clock=lambda:f.now)
        original=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash'])
        episode=dict(id=rid(),**{'from':'2026-10-10','to':'2026-12-31'},onset='before_employment',first_scheduled_day=None,
            continuation_group=rid(),recovery_before=True,unculpable=True,evidence_refs=[original])
        source=dict(employment_from='2026-10-15',employment_to=None,pay_basis='monthly',complete_from='2026-10-15',
            complete_through='2026-12-31',history_evidence_refs=[original],episodes=[episode],
            prevention_cases=[dict(id=rid(),episode_ids=[episode['id']],evidence_refs=[original])],
            employment_commencement=dict(contract_concluded_on='2026-10-01',evidence_refs=[original]))
        def save(kind,input_):
            details=dict(case_key=rid(),employment_terms_ref=reference(self.base['sources']['employment_terms']),work_schedule_refs=[],
                preparation_refs=[],agreement_refs=[reference(f.data['agreement'])],sickness_history_ref=None,input=input_,
                verification_note='Actual original pre-employment sickness and supported continuation')
            proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind=kind,details=details,source_file_ids=[original['id']])
            preview=api.preview(f.owner,proposal)
            return api.save(f.owner,dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        history=save('sickness_history',source)
        continuation=save('unpaid_continuation',dict(**{'from':'2026-10-15','to':'2026-11-11'},employment_to=None,employment_continues=True,
            no_wage_claim=True,intervening_paid_days=[],evidence_refs=[original],exceptions=[]))
        case,_=self.case(self.details()|dict(entitlement_case_refs=sorted([reference(history),reference(continuation)],key=lambda v:v['id'])))
        run=f.payroll.finalize(f.owner,self.command(case))
        return api,history,continuation,case,run

    def test_actual_preemployment_sickness_preserves_waiting_period_and_does_not_invent_prestart_wage(self):
        f=self.f;api,history,continuation,case,run=self.preemployment_zero_case()
        self.assertEqual('de_2026_sickness_start_v4',history['plan']['rule_version'])
        self.assertEqual('2026-10-15',run['calculation']['period_details']['unpaid_dates'][0])
        self.assertEqual(17,len(run['calculation']['period_details']['unpaid_dates']))
        self.assertEqual(0,run['calculation']['gross_minor']);self.assertEqual(0,run['calculation']['payout_minor'])
        self.assertEqual(17,run['calculation']['period_details']['social_periods'][0]['days'])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_time_days').fetchone()[0])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_zero_payable_requires_original_declaration_without_fictitious_cash(self):
        f=self.f;api,history,continuation,case,run=self.preemployment_zero_case()
        details=accounts_fixture.PayrollAccountTests.payment_details(f,run,f.identity,payments=[])
        f.problem(400,lambda:f.account_api()._payment_fields(details,run['calculation'],'2026-10'))
        f.problem(400,lambda:f.save_account(f.data,'payment',details,confirmed=False))
        f.problem(400,lambda:f.save_account(f.data,'payment',details|dict(standard_case_confirmed=False)))
        f.problem(400,lambda:f.save_account(f.data,'payment',details|dict(payments=[dict(paid_on='2026-10-31',amount_minor=0,payment_reference='NOT-A-PAYMENT')])) )
        payment,command=f.save_account(f.data,'payment',details)
        self.assertEqual(payment,f.account_api().save(f.owner,command))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        account=ledger['months'][9]['wage_account']
        self.assertTrue(account['complete']);self.assertEqual('no_payment_due',account['payment_status'])
        self.assertEqual([],account['payments']);self.assertEqual(0,account['payable_minor'])
        self.assertEqual(reference(payment),account['payment_ref'])
        self.assertNotIn('payment_evidence_missing',account['issues'])
        self.assertIn('unpaid_statutory_marker_requires_evidence',ledger['account_completeness_issues'])
        pdf=f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),'pdf')[0]
        self.assertIn(b'Keine Nettozahlung geschuldet',pdf)
        finance=self.finance()
        f.problem(400,lambda:finance.api.preview(f.owner,finance.body(payment)))
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_zero_net_declaration_leaves_nonzero_minijob_remittance_separately_unpaid(self):
        from decimal import Decimal
        from test_payroll_de_2026 import profile
        self.f=f=facts_fixture.PayrollFactTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        old=f.data;amount=2925
        agreement=f.hr.save_agreement(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],id=old['agreement']['id'],revision=1,
            effective_from='2026-01-01',employment_kind='minijob',pay_basis='monthly',amount_minor=amount,currency='EUR',
            reference_file_id=old['file']['id'],correction_reason='Actual small contractual wage with minimum pension contribution'))
        saved=f.payroll.save_profile(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],id=old['profile']['id'],revision=1,
            profile=profile('minijob',regular_annual_gross_minor=amount*12),source_file_id=old['file']['id'],confirmed=True,
            correction_reason='Actual minimum pension liability evidenced'))
        fresh=f.hr.preview(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        preparation=f.hr.close_preparation(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],month='2026-10',
            id=old['preparation']['id'],revision=1,source_hash=fresh['source_hash'],completeness_confirmed=True,
            correction_reason='Actual corrected small monthly contractual wage'))
        f.data=dict(old,agreement=agreement,profile=saved,preparation=preparation)
        f.identity,_=f.save_account(f.data,'identity',f.identity_details(f.data,employment_from='2026-10-15',employment_to=None))
        self.base,_,_=f.period();self.api=cases.PayrollCalculationCases(f.office,clock=lambda:f.now)
        case,_=self.case();run=f.payroll.finalize(f.owner,self.command(case))
        self.assertEqual(1604,run['calculation']['gross_minor'])
        self.assertEqual(1604,run['calculation']['employee_social_total_minor'])
        self.assertEqual(0,run['calculation']['net_minor'])
        payment,_=f.save_account(f.data,'payment',accounts_fixture.PayrollAccountTests.payment_details(f,run,f.identity,payments=[]))
        finance=self.finance()
        f.problem(400,lambda:finance.api.preview(f.owner,finance.body(payment)))
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        remittance=finance.remittance(f.data,run,payment)
        self.assertGreater(remittance['settlement']['amount_minor'],1604)
        f.problem(400,lambda:finance.api.preview(f.owner,remittance|dict(settlement=None)))
        actual=finance.import_cash(remittance)
        self.assertEqual(1,len(actual['public_source']['cash_movements']))
        self.assertEqual(remittance['settlement']['amount_minor'],int(Decimal(actual['public_source']['cash_movements'][0]['amount'])*100))
        self.assertEqual([],payment['details']['payments'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_zero_declaration_cannot_cover_corrected_nonzero_run_or_create_remittance_cash(self):
        f=self.f;api,history,continuation,case,run=self.preemployment_zero_case()
        details=accounts_fixture.PayrollAccountTests.payment_details(f,run,f.identity,payments=[])
        payment,command=f.save_account(f.data,'payment',details)
        for fact in (history,continuation):
            proposal={key:fact[key] for key in ('employee_id','kind','details')}
            proposal.update(employee_revision=f.employee['revision'],source_file_ids=[f.data['file']['id']])
            preview=api.preview(f.owner,proposal)
            api.save(f.owner,proposal|dict(request_id=rid(),id=fact['id'],revision=fact['revision'],status='void',confirmed=True,
                preview_hash=preview['preview_hash'],correction_reason='Original evidence corrected: employee was not unable to work'))
        corrected_case,_=self.case(self.details(),id=case['id'],revision=1,correction_reason='Bind corrected original claims')
        corrected=f.payroll.finalize(f.owner,self.command(corrected_case,id=run['id'],revision=1,correction_reason='Actual wage obligation restored'))
        self.assertGreater(corrected['calculation']['payout_minor'],0)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertIn('payment_evidence_missing',ledger['months'][9]['wage_account']['issues'])
        self.assertEqual(payment,f.account_api().save(f.owner,command))
        f.problem(400,lambda:f.save_account(f.data,'payment',details|dict(run_revision=2)))
        finance=self.finance()
        f.problem(409,lambda:finance.api.preview(f.owner,finance.body(payment)))
        new_payment=self.payment(corrected)
        self.assertEqual(2,new_payment['details']['run_revision'])
        current=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual('payments_evidenced',current['months'][9]['wage_account']['payment_status'])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
