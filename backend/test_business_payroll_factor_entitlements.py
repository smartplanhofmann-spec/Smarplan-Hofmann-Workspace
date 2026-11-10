"""Actual factor/P4 originals: entitlement gross is never fabricated project work."""
from copy import deepcopy
import unittest

import business_schema
from business_payroll_calculation_cases import PayrollCalculationCases
from business_payroll_entitlements import PayrollEntitlements
from business_payroll_facts import reference
from test_business_payroll import rid
import test_business_payroll_periods as periods

RULE = 'de_2026_factor_claims_month_v12'
SCOPE = 'regular_standard_factor_claims_month'


class FactorEntitlementFixture(unittest.TestCase):
    def setUp(self):
        self.parent = periods.PayrollPeriodWorkflowTests('runTest'); self.parent.setUp()
        self.addCleanup(self.parent.doCleanups); self.f = f = self.parent.f
        start = getattr(self, 'employment_start', '2026-10-01')
        f.employee = f.call(f.planning, 'save_employee', f.owner, dict(request_id=rid(),
            id=f.employee['id'], revision=f.employee['revision'], employment_from=start, employment_to=None))
        self.parent.regular(amount=getattr(self, 'monthly_amount', 500000),
            tax_class=4, special_cases=['tax_factor'], tax_factor='0.753')
        f.identity, _ = f.save_account(f.data, 'identity',
            f.identity_details(f.data, employment_from=start, employment_to=None),
            id=f.identity['id'], revision=f.identity['revision'], correction_reason='Actual full-month employment identity')
        self.terms = f.api.save(f.owner, f.body('employment_terms',
            f.terms_details() | dict(employment_from=start)))
        details = f.period_details(self.terms)
        preview = f.api.preview(f.owner, f.preview_body(details))
        self.base = f.api.save(f.owner, f.body('period_case', details, preview_hash=preview['preview_hash']))
        self.api = PayrollCalculationCases(f.office, clock=lambda:f.now)
        self.claims = PayrollEntitlements(f.office, clock=lambda:f.now)
        self.original = dict(id=f.data['file']['id'], revision=1, content_hash=f.data['file']['content_hash'])

    def unpaid(self, *, to='2026-10-24'):
        f = self.f
        details = dict(case_key=rid(), employment_terms_ref=reference(self.terms), work_schedule_refs=[],
            preparation_refs=[], agreement_refs=[reference(f.data['agreement'])], sickness_history_ref=None,
            input=dict(**{'from':'2026-10-20', 'to':to}, employment_to=None,
                employment_continues=True, no_wage_claim=True, intervening_paid_days=[],
                evidence_refs=[self.original], exceptions=[]), verification_note='Actual five unpaid calendar days')
        body = dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'],
            kind='unpaid_continuation', details=details, source_file_ids=[self.original['id']])
        preview = self.claims.preview(f.owner, body)
        self.claim = self.claims.save(f.owner, dict(body, request_id=rid(), revision=0,
            status='active', confirmed=True, preview_hash=preview['preview_hash']))
        return self.claim

    def proposal(self):
        f = self.f
        return dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'], kind='calculation_case',
            rule_version=RULE, source_contract_version=4, source_file_ids=[self.original['id']],
            details=dict(month='2026-10', period_case_ref=reference(self.base),
                employment_terms_refs=[reference(self.terms)], profile_refs=[reference(f.data['profile'])],
                identity_refs=[reference(f.identity)], segment_events=[], thirty_day_rule=None,
                entitlement_case_refs=[reference(self.claim)], travel_settlement_refs=[], flat_tax_decision=None,
                verification_note='Actual original factor and separately evidenced five unpaid days'))

    def accepted(self):
        f = self.f
        self.sources = self.api.sources(f.owner, dict(employee_id=f.employee['id'], month='2026-10'))
        self.case_input = self.proposal(); self.case_preview = self.api.preview(f.owner, self.case_input)
        self.case_command = dict(self.case_input, request_id=rid(), revision=0, status='active', confirmed=True,
            preview_hash=self.case_preview['preview_hash'])
        self.case = self.api.save(f.owner, self.case_command)
        self.run_input = dict(employee_id=f.employee['id'], source_schema_version=3, calculation_case_ref=reference(self.case))
        self.run_preview = f.payroll.preview(f.owner, self.run_input)
        self.run_command = periods.command(f.payroll, f.owner, self.run_input)
        self.run = f.payroll.finalize(f.owner, self.run_command)
        return self.run


    def hourly_public_holiday(self):
        import calendar
        f=self.f;agreement=f.data['agreement']
        f.data['agreement']=f.hr.save_agreement(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],
            id=agreement['id'],revision=agreement['revision'],effective_from='2026-01-01',employment_kind='regular',
            pay_basis='hourly',amount_minor=40000,currency='EUR',reference_file_id=self.original['id'],
            correction_reason='Actual synthetic hourly agreement; no invented work hours'))
        self.terms=f.api.save(f.owner,f.body('employment_terms',f.terms_details()|dict(employment_from='2026-10-01'),
            id=self.terms['id'],revision=self.terms['revision'],correction_reason='Actual hourly original bound'))
        schedule=f.api.save(f.owner,f.body('work_schedule',dict(month='2026-10',
            days=[dict(date='2026-10-'+str(n).zfill(2),scheduled_seconds=28800 if n==3 else 0,
                workplace='Synthetic original holiday-only work schedule',federal_state='BW')
                for n in range(1,calendar.monthrange(2026,10)[1]+1)],reason='Actual original eight scheduled holiday hours')))
        preview=f.hr.preview(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        old=f.data['preparation']
        f.data['preparation']=f.hr.close_preparation(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],
            id=old['id'],revision=old['revision'],month='2026-10',source_hash=preview['source_hash'],
            completeness_confirmed=True,correction_reason='Actual original hourly agreement adopted'))
        details=f.period_details(self.terms,work_schedule_ref=reference(schedule))
        preview=f.api.preview(f.owner,f.preview_body(details))
        self.base=f.api.save(f.owner,f.body('period_case',details,id=self.base['id'],revision=self.base['revision'],
            correction_reason='Actual original hourly month and schedule',preview_hash=preview['preview_hash']))
        details=dict(case_key=rid(),employment_terms_ref=reference(self.terms),work_schedule_refs=[reference(schedule)],
            preparation_refs=[reference(f.data['preparation'])],agreement_refs=[reference(f.data['agreement'])],
            sickness_history_ref=None,input=dict(kind='public_holiday',hourly_rate_minor=40000,evidence_refs=[self.original],
                days=[dict(date='2026-10-03',scheduled_regular_seconds=28800,worked_regular_seconds=0,
                    entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=False,evidence_refs=[self.original])]),
            verification_note='Actual German Unity Day, schedule and no adjacent unexcused absence evidenced')
        proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='regular_absence',
            details=details,source_file_ids=[self.original['id']])
        preview=self.claims.preview(f.owner,proposal)
        self.claim=self.claims.save(f.owner,dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,
            preview_hash=preview['preview_hash']))
        return self.claim


class FactorEntitlementWorkflow(FactorEntitlementFixture):
    def test_actual_partial_month_stays_blocked_without_plausible_net_or_new_run(self):
        from core import Problem
        other=FactorEntitlementFixture('runTest');other.employment_start='2026-10-15';other.setUp()
        try:
            other.unpaid();proposal=other.proposal();preview=other.api.preview(other.f.owner,proposal)
            self.assertFalse(preview['can_calculate'])
            self.assertIn('factor_claims_full_month_required',[v['code'] for v in preview['plan']['blockers']])
            case=other.api.save(other.f.owner,dict(proposal,request_id=rid(),revision=0,status='active',
                confirmed=True,preview_hash=preview['preview_hash']))
            inputs=dict(employee_id=other.f.employee['id'],source_schema_version=3,calculation_case_ref=reference(case))
            run_preview=other.f.payroll.preview(other.f.owner,inputs)
            self.assertFalse(run_preview['can_finalize']);self.assertIsNone(run_preview['calculation']['net_minor'])
            with self.assertRaises(Problem):
                other.f.payroll.finalize(other.f.owner,dict(inputs,request_id=rid(),revision=0,confirmed=True,
                    preview_hash=run_preview['preview_hash'],accepted_scope='regular_standard_factor_claims_month'))
            self.assertEqual(other.f.payroll.records(other.f.owner,'run',dict(employee_id=other.f.employee['id']))['items'],[])
        finally:other.doCleanups()

    def test_actual_hourly_public_holiday_claim_adds_only_evidenced_absence_pay(self):
        self.hourly_public_holiday();f=self.f
        before=[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')]
        run=self.accepted();self.assertEqual(run['calculation']['gross_minor'],320000)
        self.assertEqual(run['calculation']['individual_wage_tax_minor'],25391)  # Separate pinned PAP XML.
        self.assertEqual(self.base['plan']['gross_minor'],0)
        self.assertEqual(run['calculation']['period_details']['earnings'][-1]['kind'],'public_holiday')
        self.assertEqual(before,[dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_claim_gross_matches_independent_pinned_xml_vectors(self):
        import json
        from pathlib import Path
        vectors = json.loads((Path(__file__).parent/'testdata/payroll_factor_entitlements_2026.json').read_text())
        expected = {row['input']['gross_minor']:row for row in vectors['cases']}
        for monthly, to, gross in ((499999,'2026-10-24',419354),
                (500001,'2026-10-24',419356),(500000,'2026-10-22',451613)):
            with self.subTest(monthly=monthly, unpaid_to=to):
                other = FactorEntitlementFixture('runTest'); other.monthly_amount = monthly
                other.setUp()
                try:
                    other.unpaid(to=to); run = other.accepted(); c = run['calculation']
                    self.assertEqual(c['gross_minor'], gross)
                    self.assertEqual(c['individual_wage_tax_minor'], expected[gross]['expected']['LSTLZZ'])
                    self.assertEqual(c['solidarity_minor'], expected[gross]['expected']['SOLZLZZ'])
                    self.assertTrue(business_schema.validate_integrity(other.f.office))
                finally: other.doCleanups()

    def test_omitted_or_stale_claim_cannot_be_finalized_and_old_original_remains_readable(self):
        from core import Problem, canonical
        f = self.f; self.unpaid(); self.accepted()
        original_run = canonical(self.run)
        omitted = deepcopy(self.case_input); omitted['details']['entitlement_case_refs'] = []
        with self.assertRaises(Problem) as failure: self.api.preview(f.owner, omitted)
        self.assertEqual(failure.exception.status, 409)
        changed = deepcopy(self.claim['details']); changed['input']['to'] = '2026-10-22'
        body = dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],
            kind='unpaid_continuation',details=changed,source_file_ids=[self.original['id']])
        preview = self.claims.preview(f.owner, body)
        updated = self.claims.save(f.owner,dict(body,request_id=rid(),id=self.claim['id'],
            revision=self.claim['revision'],status='active',confirmed=True,
            correction_reason='Actual original unpaid period corrected to three days',preview_hash=preview['preview_hash']))
        with self.assertRaises(Problem) as failure: self.api.preview(f.owner,self.case_input)
        self.assertEqual(failure.exception.status,409)
        # An exact accepted retry still returns the original, never a fresh calculation.
        self.assertEqual(canonical(f.payroll.finalize(f.owner,self.run_command)),original_run)
        self.assertEqual(f.payroll.get(f.owner,'run',self.run['id']),self.run)
        self.assertNotEqual(updated['content_hash'],self.claim['content_hash'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_unknown_contract_partial_month_and_unbound_factor_do_not_create_payroll(self):
        from core import Problem
        from payroll_factor_claims_2026 import build_plan
        f=self.f; self.unpaid(); preview=self.api.preview(f.owner,self.proposal())
        for value in (True,1,2,3,5):
            wrong=self.proposal();wrong['source_contract_version']=value
            with self.subTest(contract=value), self.assertRaises(Problem):self.api.preview(f.owner,wrong)
        changed=deepcopy(preview['source_snapshot']);changed['profiles'][0]['profile']['tax_factor']='0.900'
        with self.assertRaises(Problem):build_plan(changed)
        # An unsupported new plan never exposes plausible financial totals.
        changed=deepcopy(preview['source_snapshot']);changed['entitlements']=[]
        from payroll_factor_claims_2026 import calculate_source
        result=calculate_source(changed)
        self.assertEqual(result['scope'],'unsupported')
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertIsNone(result['net_minor']);self.assertIsNone(result['employee_contributions'])
        with self.assertRaises(Problem) as failure:
            self.api.sources(f.technician,dict(employee_id=f.employee['id'],month='2026-10'))
        self.assertEqual(failure.exception.status,403)
        self.assertEqual(f.payroll.records(f.owner,'run',dict(employee_id=f.employee['id']))['items'],[])

    def test_actual_payment_private_statement_annual_and_euer_use_the_claim_gross_once(self):
        from business_payroll_annual_basis import PayrollAnnualBasis
        from business_payroll_statements import PayrollStatements
        import test_business_payroll_accounts as accounts
        import test_business_payroll_calculations as calculation_fixture
        f = self.f; self.unpaid(); run = self.accepted()
        details = accounts.PayrollAccountTests.payment_details(f, run, f.identity,
            payments=[dict(paid_on='2026-10-31', amount_minor=285054, payment_reference='SYN-ACTUAL-FACTOR-CLAIMS-NET')])
        paid, payment_command = f.save_account(f.data, 'payment', details)
        self.assertEqual(f.account_api().save(f.owner, payment_command), paid)
        finance = calculation_fixture.CalculationPayrollWorkflow.finance(self)
        cash = finance.import_cash(finance.body(paid)); finance.post('payroll_cash', finance.payload(cash))
        self.assertEqual(finance.euer.report(f.owner, 2026)['totals']['confirmed_expenses'], '2850.54')
        own = PayrollStatements(f.office).get(f.technician, run['id'])['statement']
        self.assertEqual(own['calculation']['net_minor'], 285054)
        self.assertNotIn(self.claim['id'], str(own)); self.assertNotIn(self.original['id'], str(own))
        self.assertTrue(f.payroll.ledger(f.owner, dict(employee_id=f.employee['id'], year='2026'))['ledger']['months'][9]['wage_account']['complete'])
        annual = PayrollAnnualBasis(f.office, clock=lambda:f.now)
        details = dict(employer_identity_ref=reference(f.identity), verification_note='Actual original factor wage, cash and yearly completeness',
            year=2026, coverage_to='2026-10-31', as_of_date='2026-10-31', payroll_run_refs=[reference(run)],
            payroll_payment_refs=[reference(paid)], imported_period_refs=[], imported_one_off_refs=[],
            current_calculation_case_ref=None,
            gaps=[dict(start='2026-01-01', end='2026-09-30', reason='not_employed', evidence_ref=self.original)], completeness_confirmed=True)
        proposal = dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'], kind='annual_basis',
            details=details, source_file_ids=[self.original['id']])
        preview = annual.preview(f.owner, proposal)
        saved = annual.save(f.owner, dict(proposal, request_id=rid(), revision=0, status='active', confirmed=True,
            preview_hash=preview['preview_hash']))
        self.assertEqual(saved['plan']['running_taxable_minor'], 419355)
        self.assertEqual(saved['plan']['section_rooms']['regular']['health']['sv_days'], 30)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_factor_month_consumes_unpaid_claim_without_changing_approved_project_time(self):
        f = self.f; self.unpaid()
        before = [dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')]
        proposal = self.proposal(); preview = self.api.preview(f.owner, proposal)
        self.assertEqual(preview['plan']['gross_minor'], 419355)  # 500000 * 26/31, rounded once.
        self.assertTrue(preview['plan']['can_calculate'], preview['plan']['blockers'])
        self.assertEqual(preview['source_snapshot']['profiles'], [f.data['profile']])
        command = dict(proposal, request_id=rid(), revision=0, status='active', confirmed=True,
            preview_hash=preview['preview_hash'])
        case = self.api.save(f.owner, command)
        inputs = dict(employee_id=f.employee['id'], source_schema_version=3, calculation_case_ref=reference(case))
        run_preview = f.payroll.preview(f.owner, inputs)
        self.assertTrue(run_preview['calculation']['payroll_calculation_complete'], run_preview['calculation']['blockers'])
        self.assertEqual(run_preview['calculation']['scope'], SCOPE)
        self.assertEqual(run_preview['calculation']['tax_parameters']['tax_factor'], '0.753')
        self.assertEqual(run_preview['calculation']['individual_wage_tax_minor'], 43091)  # Separate pinned XML/Java oracle.
        self.assertEqual(run_preview['calculation']['employee_contributions']['care'], 10064)  # 75.48 + 25.16, GKV two-step.
        self.assertEqual(run_preview['calculation']['employee_social_total_minor'], 91210)
        self.assertEqual(run_preview['calculation']['net_minor'], 285054)
        accepted = periods.command(f.payroll, f.owner, inputs)
        run = f.payroll.finalize(f.owner, accepted)
        self.assertEqual(run['calculation']['gross_minor'], 419355)
        self.assertEqual(f.payroll.finalize(f.owner, accepted), run)
        self.assertEqual(self.api.save(f.owner, command), case)
        self.assertEqual(before, [dict(row) for row in f.office.db.execute('SELECT * FROM business_time_days')])
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__ == '__main__': unittest.main()
