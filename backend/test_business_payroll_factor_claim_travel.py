"""Actual full factor month, complete P4 originals and separately paid travel."""
from pathlib import Path
from copy import deepcopy
import hashlib
import unittest

from cryptography.fernet import Fernet
from core import Problem, canonical
from business_accounting import Accounting
from business_payroll_facts import reference
from business_travel_allowances import TravelAllowances
from online.instance import bind
from online.storage import Storage
import test_business_payroll_factor_entitlements as entitlement_fixture
import test_business_travel_allowances as travel_fixture
from travel_allowance_cash import record_payment
from test_business_planning import rid

RULE = 'de_2026_factor_claims_paid_travel_month_v13'
CONTRACT = 5
SCOPE = 'regular_standard_factor_claims_paid_travel_month'


class FactorClaimTravelFixture(entitlement_fixture.FactorEntitlementFixture):
    def setUp(self):
        super().setUp()
        if not getattr(self,'defer_claim',False):
            self.unpaid()
        f = self.f
        self.travel = t = travel_fixture.TravelWorkflowTests('runTest')
        for key in ('office', 'owner', 'technician', 'employee', 'project', 'now', 'temporary', 'hr'):
            setattr(t, key, getattr(f, key))
        t.api = TravelAllowances(f.office, clock=lambda:f.now)
        t.file = t.upload(purpose='expense_receipt', actor=f.technician, visible=True)
        t.home = t.save_site('home'); t.place = t.save_site('external_fixed')
        t.instance = rid(); key = Fernet.generate_key()
        self.storage = Storage(f.office, key, 'factor-claim-travel.example.test',
            config={'server': {'path':str(Path(f.temporary.name)/'company')}})
        bind(f.office, t.instance, 'factor-claim-travel.example.test', key, self.storage)
        t.account = Accounting(f.office, clock=lambda:f.now).create_account(f.owner,
            dict(request_id=rid(), confirmation=True, code='1200', name='Synthetic actual travel bank', kind='bank'))
        self.settlement = t.api.approve(f.owner, t.approval(t.submitted()))['result']
        self.payment_command = t.payment(self.settlement, 1400)
        self.payment = record_payment(t.api, f.owner, self.payment_command)['result']

    def proposal(self):
        body = super().proposal()
        body.update(rule_version=RULE, source_contract_version=CONTRACT)
        body['details'].update(travel_settlement_refs=[reference(self.settlement)],
            travel_payment_refs=[reference(self.payment)],
            verification_note='Actual original full factor month, all P4 originals and already paid taxfree travel')
        return body

    def save_case(self,body,previous=None):
        preview=self.api.preview(self.f.owner,body)
        command=dict(body,request_id=rid(),revision=previous['revision'] if previous else 0,
                     status='active',confirmed=True,preview_hash=preview['preview_hash'])
        if previous:
            command.update(id=previous['id'],correction_reason='Explicitly add only the missing original component to this unused factor case')
        return self.api.save(self.f.owner,command),command


class FactorClaimTravelWorkflow(FactorClaimTravelFixture):
    def test_actual_factor_claim_gross_and_paid_travel_have_one_explicit_composed_contract(self):
        f = self.f
        before = [dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')]
        original_payment = dict(self.payment)
        preview = self.api.preview(f.owner, self.proposal())
        self.assertTrue(preview['can_calculate'], preview['plan']['blockers'])
        self.assertEqual(preview['plan']['rule_version'], RULE)
        self.assertEqual(preview['plan']['source_contract_version'], CONTRACT)
        self.assertEqual(preview['plan']['gross_minor'], 419355)
        self.assertEqual(preview['plan']['travel_paid_minor'], 1400)
        self.assertEqual(before, [dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')])
        self.assertEqual(self.travel.api._get('payment', self.payment['id']), original_payment)

    def test_actual_source3_run_preserves_claim_net_and_never_adds_already_paid_travel(self):
        from business_payroll import validate_integrity as validate_runs
        from business_payroll_calculation_cases import validate_integrity as validate_cases
        run = self.accepted()
        calculation = run['calculation']
        self.assertEqual(calculation['scope'], SCOPE)
        self.assertEqual(calculation['gross_minor'], 419355)
        self.assertEqual(calculation['individual_wage_tax_minor'], 43091)
        self.assertEqual(calculation['employee_social_total_minor'], 91210)
        self.assertEqual(calculation['net_minor'], 285054)
        self.assertEqual(calculation['payout_minor'], 285054)
        self.assertFalse(calculation['travel_expenses_included_in_net'])
        self.assertEqual(calculation['period_details']['travel_paid_minor'], 1400)
        self.assertEqual(self.base['plan']['gross_minor'], 500000)
        self.assertTrue(validate_runs(self.f.office));self.assertTrue(validate_cases(self.f.office))
        self.assertEqual(self.f.payroll.finalize(self.f.owner,self.run_command),run)

    def test_original_component_snapshots_are_explicit_projections_and_outer_hash_binds_both(self):
        from payroll_factor_claim_travel_2026 import projections,build_plan
        import payroll_factor_claims_2026 as claims
        import payroll_factor_taxfree_travel_2026 as travel
        preview=self.api.preview(self.f.owner,self.proposal())
        snapshot=preview['source_snapshot'];original=deepcopy(snapshot)
        wage,proof=projections(snapshot)
        self.assertEqual(wage['entitlements'],snapshot['entitlements'])
        self.assertEqual(proof['travel_sources'],snapshot['travel_sources'])
        self.assertEqual(wage['travel_sources'],[]);self.assertEqual(proof['entitlements'],[])
        for key in ('period_case','employment_terms','profiles','identities','source_files'):
            self.assertEqual(wage[key],snapshot[key]);self.assertEqual(proof[key],snapshot[key])
        plan=build_plan(snapshot)
        self.assertEqual(plan['components']['claims']['plan_hash'],claims.build_plan(wage)['plan_hash'])
        self.assertEqual(plan['components']['paid_travel']['plan_hash'],travel.build_plan(proof)['plan_hash'])
        self.assertEqual(plan['source_snapshot_hash'],hashlib.sha256(canonical(snapshot).encode()).hexdigest())
        self.assertEqual(snapshot,original)

    def test_claim_and_payment_omissions_unknown_contract_and_mismatched_payment_are_rejected(self):
        body=self.proposal()
        for field,value in (('source_contract_version',4),('source_contract_version',6),('rule_version','de_2026_factor_claims_month_v12')):
            changed=deepcopy(body);changed[field]=value
            with self.assertRaises(Problem):self.api.preview(self.f.owner,changed)
        for name in ('entitlement_case_refs','travel_payment_refs'):
            changed=deepcopy(body);changed['details'][name]=[]
            with self.assertRaises(Problem):self.api.preview(self.f.owner,changed)
        changed=deepcopy(body);changed['details']['travel_payment_refs'][0]['content_hash']='0'*64
        with self.assertRaises(Problem):self.api.preview(self.f.owner,changed)

    def test_unused_v12_original_may_add_only_its_actual_paid_travel_component(self):
        from business_payroll_calculation_cases import validate_integrity
        original_body=entitlement_fixture.FactorEntitlementFixture.proposal(self)
        original,_=self.save_case(original_body)
        saved,command=self.save_case(self.proposal(),original)
        self.assertEqual(saved['revision'],2);self.assertEqual(saved['id'],original['id'])
        self.assertEqual(saved['previous_hash'],original['content_hash'])
        self.assertEqual(self.api._get(original['id'],1),original)
        self.assertEqual(self.api.save(self.f.owner,command),saved)
        self.assertTrue(validate_integrity(self.f.office))

    def test_unused_v10_original_may_add_only_actual_complete_p4_component(self):
        import test_payroll_factor_taxfree_travel as travel_factor_fixture
        from business_payroll_calculation_cases import validate_integrity
        other=FactorClaimTravelFixture('runTest');other.defer_claim=True;other.setUp()
        try:
            f=other.f
            body=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='calculation_case',
                rule_version='de_2026_factor_taxfree_travel_month_v10',source_contract_version=2,
                details=travel_factor_fixture.FactorTravelFixture.details(other),source_file_ids=[other.original['id']])
            original,_=other.save_case(body)
            other.unpaid()
            saved,_=other.save_case(other.proposal(),original)
            self.assertEqual(saved['revision'],2)
            self.assertEqual(saved['sources']['travel_sources'],original['sources']['travel_sources'])
            self.assertEqual(other.api._get(original['id'],1),original)
            self.assertTrue(validate_integrity(f.office))
        finally:other.doCleanups()

    def test_previously_used_v12_case_cannot_be_relabelled_as_unused(self):
        import test_business_payroll_periods as periods
        f=self.f;original,_=self.save_case(entitlement_fixture.FactorEntitlementFixture.proposal(self))
        inputs=dict(employee_id=f.employee['id'],source_schema_version=3,calculation_case_ref=reference(original))
        run=f.payroll.finalize(f.owner,periods.command(f.payroll,f.owner,inputs))
        body=self.proposal();preview=self.api.preview(f.owner,body)
        command=dict(body,request_id=rid(),id=original['id'],revision=original['revision'],status='active',
            confirmed=True,preview_hash=preview['preview_hash'],correction_reason='This used original must stay under its own rule')
        with self.assertRaises(Problem) as caught:self.api.save(f.owner,command)
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(self.api._get(original['id']),original)
        self.assertEqual(f.payroll.get(f.owner,'run',run['id']),run)

    def test_missing_whole_dependency_journal_cannot_prove_that_an_original_was_unused(self):
        from business_payroll_annual_basis import TABLES as annual_tables
        from payroll_factor_claim_travel_sources import require_unused_upgrade
        original,_=self.save_case(entitlement_fixture.FactorEntitlementFixture.proposal(self))
        current=self.api.preview(self.f.owner,self.proposal())
        candidate=dict(original,rule_version=RULE,source_contract_version=CONTRACT,
            sources=current['source_snapshot'],plan=current['plan'])
        # Actual incomplete historical database, not a fabricated empty result.
        # A missing entire additive module is allowed by its old validator,
        # but cannot establish non-use for a new contract transition.
        for table in annual_tables:self.f.office.db.execute('DROP TABLE '+table)
        with self.assertRaises(Problem) as caught:require_unused_upgrade(self.api,original,candidate)
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(self.api._get(original['id']),original)

    def test_actual_payment_euer_private_statement_and_annual_basis_keep_travel_separate(self):
        import business_schema
        from business_accounting_profile import AccountingPreparationProfile
        from business_accounting_euer import EuerAccounting
        from business_payroll_cash import PayrollCash
        from business_payroll_statements import PayrollStatements
        from business_payroll_annual_basis import PayrollAnnualBasis
        from travel_allowance_cash import public_source
        import test_business_payroll_cash as cash_fixture
        import test_business_payroll_accounts as accounts
        f=self.f;run=self.accepted()
        profile=AccountingPreparationProfile(f.office,clock=lambda:f.now);state=profile.state(f.owner)
        data=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Actual original EÜR facts checked',
            evidence_reference='Synthetic actual owner evidence',profile=dict(legal_form='sole_proprietorship',accounting_method='euer',
                vat_regime='regular',vat_timing='cash',vat_effective_from='2026-01-01',bookkeeping_start='2026-01-01'))
        preview=profile.preview(f.owner,data)
        profile.confirm(f.owner,dict(data,request_id=rid(),confirmation=True,preview_hash=preview['preview_hash']))
        helper=cash_fixture.PayrollCashTests('runTest');helper.office=f.office;helper.owner=f.owner;helper.f=f
        helper.instance=self.travel.instance;helper.account=self.travel.account
        helper.api=PayrollCash(f.office,clock=lambda:f.now);helper.euer=EuerAccounting(f.office,clock=lambda:f.now)
        details=accounts.PayrollAccountTests.payment_details(f,run,f.identity,
            payments=[dict(paid_on='2026-10-31',amount_minor=285054,payment_reference='SYN-ACTUAL-COMPOSED-CLAIM-NET')])
        paid,payment_command=f.save_account(f.data,'payment',details)
        self.assertEqual(f.account_api().save(f.owner,payment_command),paid)
        net=helper.import_cash(helper.body(paid));helper.post('payroll_cash',helper.payload(net))
        self.assertEqual(helper.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'2850.54')
        travel=public_source(f.office,self.payment['id'])
        helper.post('travel_cash',dict(payment_id=self.payment['id'],revision=1,source_hash=travel['source_hash'],accounts={'travel_allowance':'6664'}))
        report=helper.euer.report(f.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],'2864.54')
        self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],1)
        own=PayrollStatements(f.office).get(f.technician,run['id'])['statement']
        self.assertEqual(own['calculation']['net_minor'],285054)
        for original in (self.claim['id'],self.original['id'],self.case['id'],self.settlement['id'],self.payment['id']):
            self.assertNotIn(original,str(own))
        annual=PayrollAnnualBasis(f.office,clock=lambda:f.now)
        details=dict(employer_identity_ref=reference(f.identity),verification_note='Actual factor claim wage, original paid travel and complete yearly evidence',
            year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[reference(run)],
            payroll_payment_refs=[reference(paid)],imported_period_refs=[],imported_one_off_refs=[],current_calculation_case_ref=None,
            gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=self.original)],completeness_confirmed=True)
        body=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='annual_basis',details=details,source_file_ids=[self.original['id']])
        preview=annual.preview(f.owner,body)
        saved=annual.save(f.owner,dict(body,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        self.assertEqual(saved['plan']['running_taxable_minor'],419355)
        self.assertEqual(saved['plan']['section_rooms']['regular']['health']['sv_days'],30)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_hourly_holiday_and_paid_trip_never_create_fictitious_work(self):
        other=FactorClaimTravelFixture('runTest');other.defer_claim=True;other.setUp()
        try:
            other.hourly_public_holiday();f=other.f
            before=[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')]
            run=other.accepted();calculation=run['calculation']
            self.assertEqual(other.base['plan']['gross_minor'],0)
            self.assertEqual(calculation['gross_minor'],320000)
            self.assertEqual(calculation['individual_wage_tax_minor'],25391)  # Pinned independent XML vector.
            self.assertEqual(calculation['period_details']['travel_paid_minor'],1400)
            self.assertFalse(calculation['travel_expenses_included_in_net'])
            self.assertEqual(before,[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')])
            earnings=calculation['period_details']['earnings']
            self.assertEqual(len(earnings),2)
            self.assertEqual(earnings[0]['gross_minor'],0)
            self.assertEqual(earnings[0]['claim_dates'],[])
            self.assertEqual(earnings[1]['kind'],'public_holiday')
            self.assertEqual(earnings[1]['gross_minor'],320000)
            self.assertEqual(calculation['period_details']['satisfied_travel_component_wage_reviews'],['zero_earnings_requires_review'])
        finally:other.doCleanups()

    def test_positive_p4_only_satisfies_zero_work_review_and_never_other_travel_guards(self):
        from payroll_factor_claim_travel_2026 import calculate_source
        other=FactorClaimTravelFixture('runTest');other.defer_claim=True;other.setUp()
        try:
            other.hourly_public_holiday()
            source=other.api.preview(other.f.owner,other.proposal())['source_snapshot']
            changed=deepcopy(source);changed['travel_sources'][0]['letter_m']=True
            # Changing a frozen travel marker already violates its source hash;
            # it must fail before any plausible payout can be returned.
            with self.assertRaises(Problem) as caught:calculate_source(changed)
            self.assertEqual(caught.exception.status,409)
            changed=deepcopy(source);changed['entitlements']=[]
            with self.assertRaises(Problem) as missing:calculate_source(changed)
            self.assertEqual(missing.exception.status,400)
        finally:other.doCleanups()


if __name__ == '__main__':
    unittest.main()
