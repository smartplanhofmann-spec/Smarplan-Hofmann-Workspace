"""V6 development composition using genuinely accepted private source records."""
from copy import deepcopy
import unittest

from core import Problem
from business_payroll_facts import reference
from business_payroll_calculation_cases import PayrollCalculationCases, CALCULATION_RULE_VERSION
from payroll_oneoff_composition_2026 import calculate_oneoff_source, ONEOFF_RULE_VERSION
from payroll_calculations_2026 import calculate_calculation_source
from payroll_pap_oneoff_2026 import calculate_standard_one_off_tax
from payroll_annual_basis_2026 import build_annual_plan
from test_business_payroll import rid
import test_business_payroll_annual_basis as fixture


def calculate(value, **changes):
    return calculate_oneoff_source(value, **(dict(rule_version=ONEOFF_RULE_VERSION, source_contract_version=1) | changes))


class OneoffCompositionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.PayrollAnnualBasisTests('runTest'); self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def source(self, *, january=False, bonus=50000, previous=False, historical_additional='1.100', flat_travel=False, shifted=False):
        f = self.f; month = '2026-01' if january else '2026-10'
        start = month + '-15'; end = month + '-31'
        if january:
            f.employee = f.call(f.planning, 'save_employee', f.owner, dict(request_id=rid(),
                id=f.employee['id'], revision=f.employee['revision'], employment_from=start))
        f.regular_contract()
        if january:
            f.identity, _ = f.save_account(f.data, 'identity', f.identity_details(f.data,
                employment_from=start, employment_to=None), id=f.identity['id'],
                revision=f.identity['revision'], correction_reason='Tatsächlichen Januar-Beschäftigungsbeginn gebunden')
        prepared = f.hr.preview(f.owner, dict(employee_id=f.employee['id'], month=month))
        command = dict(request_id=rid(), employee_id=f.employee['id'], month=month,
            revision=0, source_hash=prepared['source_hash'], completeness_confirmed=True)
        if not january:
            command.update(id=f.data['preparation']['id'], revision=f.data['preparation']['revision'],
                correction_reason='Regulären tatsächlichen Originalvertrag in Monatsquelle gebunden')
        f.data['preparation'] = f.hr.close_preparation(f.owner, command)
        td = f.terms_details(); td['employment_from'] = start
        terms = f.api.save(f.owner, f.body('employment_terms', td))
        pd = f.period_details(terms); pd['month'] = month
        pv = f.api.preview(f.owner, f.preview_body(pd))
        base = f.api.save(f.owner, f.body('period_case', pd, preview_hash=pv['preview_hash']))
        api = PayrollCalculationCases(f.office, clock=lambda: f.now)
        details = dict(month=month, period_case_ref=reference(base), employment_terms_refs=[reference(terms)],
            profile_refs=[reference(f.data['profile'])], identity_refs=[reference(f.identity)],
            segment_events=[], thirty_day_rule=None, entitlement_case_refs=[], travel_settlement_refs=[],
            flat_tax_decision=None, verification_note='Actual regular case for one-off composition')
        if flat_travel:
            import test_business_payroll_calculations as travel_fixture
            import test_business_payroll_calculation_cases as policy_fixture
            self.api = api
            _, settlement = travel_fixture.CalculationPayrollWorkflow.travel(self)
            policy, _ = policy_fixture.CalculationCaseTests.policy(self, employer_bears_tax=not shifted)
            details.update(travel_settlement_refs=[reference(settlement)], flat_tax_decision=dict(
                policy_ref=reference(policy), church_membership_evidence=None,
                employee_deduction_file_ref=f.original if shifted else None,
                tax_certificate_file_ref=None, tax_certificate_issued_on=None, record_on_finalize=True))
        request = dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'],
            kind='calculation_case', rule_version=CALCULATION_RULE_VERSION, source_contract_version=1,
            details=details, source_file_ids=[f.original['id']])
        pv = api.preview(f.owner, request)
        current = api.save(f.owner, request | dict(request_id=rid(), revision=0, status='active',
            confirmed=True, preview_hash=pv['preview_hash']))
        gaps = [] if january else [dict(start='2026-01-01', end='2026-09-30',
            reason='not_employed', evidence_ref=f.original)]
        bd = f.basis_details(current, imported_period_refs=[], current_calculation_case_ref=reference(current),
            coverage_to=end, as_of_date=end, gaps=gaps)
        annual, _, _ = f.save('annual_basis', bd)
        ed = f.claim_details(terms); ed.update(planned_receipt_date=end, amount_minor=bonus,
            claim_periods=[dict(start=start, end=end, evidence_ref=f.original)])
        earning, _, _ = f.save('one_off_earning', ed)
        fd = f.forecast_details(annual, earning, terms); fd['receipt_date'] = end
        fd['remaining_periods'] = [dict(month='2026-' + format(index, '02'),
            employment_terms_ref=reference(terms), agreement_refs=[reference(f.data['agreement'])],
            work_schedule_ref=None) for index in range(int(month[-2:]) + 1, 13)]
        forecast, _, _ = f.save('annual_tax_forecast', fd)
        prior = None
        if previous:
            imported = f.imported_details()
            imported.update(period_start='2025-12-01', period_end='2025-12-31', employment_from='2025-12-01',
                running_gross_minor=200000, running_taxable_minor=200000,
                running_receipts=[dict(received_on='2025-12-31', taxable_minor=200000, evidence_ref=f.original)],
                original_payroll_reference='Actual prior-December synthetic original')
            imported['profile'].update(health_additional_percent=historical_additional,
                saxony=True, childless_surcharge=False, care_child_discounts=1)
            for item in imported['branches'].values():
                item.update(total_minor=200000, employee_minor=200000,
                    eligible_intervals=[dict(start='2025-12-01', end='2025-12-31',
                        legal_reason='paid_employment', evidence_ref=f.original)])
            if previous == 'minijob':
                imported.update(section_key='minijob', running_gross_minor=50000, running_taxable_minor=0, running_receipts=[])
                imported['profile']['scheme'] = 'commercial_minijob'
                for branch, item in imported['branches'].items():
                    item.update(total_minor=50000, employee_minor=50000)
                    if branch in ('care', 'unemployment'):
                        item.update(total_minor=0, employee_minor=0, eligible_intervals=[])
            original, _, _ = f.save('imported_period', imported)
            prior, _, _ = f.save('annual_basis', f.basis_details(original, year=2025,
                coverage_to='2025-12-31', as_of_date=end, gaps=[dict(start='2025-01-01', end='2025-11-30',
                    reason='not_employed', evidence_ref=f.original)]))
        return dict(schema_version=1, source_contract_version=1, rule_version=ONEOFF_RULE_VERSION,
            employee_id=f.employee['id'], month=month, running_calculation_case=current,
            one_off_earning=earning, current_annual_basis=annual, previous_annual_basis=prior,
            annual_tax_forecast=forecast)

    def test_actual_regular_current_case_conserves_money_without_retaxing_running_wages(self):
        source = self.source(); before = deepcopy(source); result = calculate(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        running = result['running_calculation']; extra = result['one_off_details']
        self.assertEqual(extra['assignment']['reason'], 'current_year_last_period')
        self.assertEqual(extra['assignment']['bases_minor'], dict.fromkeys(('health', 'care', 'pension', 'unemployment'), 50000))
        self.assertEqual(extra['social']['employee_contributions'], dict(health_general=3650,
            health_additional=725, pension=4650, unemployment=650, care=1200))
        self.assertEqual(extra['social']['employer_levies'], dict(u1=0, u2=0, insolvency=75))
        self.assertEqual(result['net_minor'], running['net_minor'] + 50000 - 10875 - extra['tax']['STS'] - extra['tax']['SOLZS'])
        self.assertEqual(result['gross_minor'], result['employee_tax_minor'] + result['employee_social_total_minor'] + result['net_minor'])
        self.assertEqual(source, before)
        exact = calculate_calculation_source(source['running_calculation_case']['sources'],
            rule_version=CALCULATION_RULE_VERSION, source_contract_version=1)
        self.assertEqual(running, exact)

    def test_march_clause_uses_2025_social_profile_and_current_2026_tax_profile(self):
        source = self.source(january=True, bonus=200000, previous=True)
        result = calculate(source); self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        extra = result['one_off_details']; assignment = extra['assignment']
        self.assertEqual((assignment['tax_year'], assignment['social_year'], assignment['march_clause']), (2026, 2025, True))
        self.assertEqual(assignment['assigned_period_end'], '2025-12-31')
        self.assertEqual(extra['social']['employee_contributions'], dict(health_general=14600,
            health_additional=1100, pension=18600, unemployment=2600, care=4100))
        self.assertEqual(extra['social']['employer_contributions']['care'], 2600)
        expected = calculate_standard_one_off_tax(annual_pay_before_minor=source['annual_tax_forecast']['plan']['annual_pay_before_minor'],
            one_off_minor=200000, tax_class=1, children_half_units=0, additional_health_percent='2.90',
            saxony=False, childless_surcharge=True, care_child_discounts=0, church_member=False,
            annual_allowance_minor=0, annual_addition_minor=0)
        self.assertEqual(extra['tax'], expected)

    def test_missing_prior_year_is_not_an_invented_nonemployment_or_zero_net(self):
        source = self.source(january=True, bonus=200000)
        result = calculate(source)
        self.assertFalse(result['payroll_calculation_complete']); self.assertIsNone(result['net_minor'])
        self.assertIn('previous_year_evidence_required', [item['code'] for item in result['blockers']])

    def test_explicit_complete_no_prior_employment_keeps_current_year_assignment(self):
        source = self.source(january=True, bonus=200000); f = self.f
        d = f.basis_details(source['running_calculation_case'], year=2025, coverage_to='2025-12-31',
            as_of_date='2026-01-31', imported_period_refs=[], gaps=[dict(start='2025-01-01', end='2025-12-31',
                reason='not_employed', evidence_ref=f.original)])
        source['previous_annual_basis'], _, _ = f.save('annual_basis', d)
        result = calculate(source); self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        self.assertFalse(result['one_off_details']['assignment']['march_clause'])
        self.assertEqual(result['one_off_details']['assignment']['social_year'], 2026)
        self.assertLess(result['one_off_details']['assignment']['bases_minor']['health'], 200000)

    def test_changed_forecast_sum_or_different_bound_case_is_rejected(self):
        source = self.source()
        bad = deepcopy(source); bad['annual_tax_forecast']['plan']['annual_pay_before_minor'] += 1
        with self.assertRaises(Problem): calculate(bad)
        bad = deepcopy(source); bad['running_calculation_case']['content_hash'] = '9' * 64
        with self.assertRaises(Problem): calculate(bad)

    def test_explicit_rule_contract_and_shape_never_fall_back_to_latest(self):
        source = self.source()
        for changes in (dict(rule_version=CALCULATION_RULE_VERSION), dict(source_contract_version=2), dict(source_contract_version=True)):
            with self.subTest(changes=changes), self.assertRaises(Problem): calculate(source, **changes)
        with self.assertRaises(Problem): calculate(source | dict(annual_pay_before_minor=0))

    def test_current_projection_cannot_be_rehashed_to_invent_additional_social_room(self):
        source = self.source(); basis = source['current_annual_basis']
        projection = basis['sources']['internal_periods'][0]
        projection['periods'][0]['branches']['health']['contributed_minor'] = 0
        basis['plan'] = build_annual_plan(basis['sources'])
        forecast = source['annual_tax_forecast']; forecast['sources']['annual_basis'] = basis
        forecast['plan'] = build_annual_plan(forecast['sources'])
        with self.assertRaises(Problem): calculate(source)

    def test_bounded_bonus_uses_distinct_health_and_pension_room(self):
        source = self.source(bonus=500000); result = calculate(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        bases = result['one_off_details']['assignment']['bases_minor']
        self.assertEqual(bases, dict(health=164859, care=164859, pension=314317, unemployment=314317))
        self.assertEqual(result['gross_minor'], 664516)

    def test_prior_minijob_is_not_silently_treated_as_no_prior_employment(self):
        result = calculate(self.source(january=True, previous='minijob'))
        self.assertFalse(result['payroll_calculation_complete']); self.assertIsNone(result['net_minor'])
        self.assertIn('mixed_oneoff_sections_required', [value['code'] for value in result['blockers']])

    def test_actual_flat_travel_and_authorized_tax_shift_preserve_one_off_payout(self):
        result = calculate(self.source(flat_travel=True, shifted=True))
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        running = result['running_calculation']; extra = result['one_off_details']
        self.assertEqual(running['period_details']['travel']['flat_taxable_payroll_minor'], 400)
        self.assertEqual(running['gross_minor'], 164916)
        self.assertGreater(running['net_deductions_minor'], 0)
        self.assertEqual(result['net_deductions_minor'], running['net_deductions_minor'])
        self.assertEqual(result['payout_minor'], running['payout_minor'] + 50000
            - extra['social']['employee_total_minor'] - extra['tax']['STS'] - extra['tax']['SOLZS'] - extra['church_tax_minor'])
        self.assertEqual(result['employer_flat_tax_minor'], running['employer_flat_tax_minor'])


if __name__ == '__main__':
    unittest.main()
