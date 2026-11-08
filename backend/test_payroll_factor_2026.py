import unittest

from core import Problem
from payroll_de_2026 import calculate, normalize_profile, RULE_VERSION, FULL_RULE_VERSION
from payroll_factor_2026 import FACTOR_RULE_VERSION, FACTOR_RULES_SHA256
from test_payroll_de_2026 import profile


def factor_profile(**changes):
    result = profile('regular', tax_class=4, health_additional_percent='2.90',
        tax_allowance_monthly_minor=0, tax_addition_monthly_minor=0,
        regular_annual_gross_minor=6000000, special_cases=['tax_factor'],
        tax_factor='0.753')
    result.update(changes)
    return result


class FactorMonthly2026(unittest.TestCase):
    def test_factor_month_uses_new_version_and_keeps_standard_social_components(self):
        p = factor_profile()
        result = calculate(p, '2026-10', 500000, full_month_confirmed=True)
        base = {k:v for k,v in p.items() if k != 'tax_factor'}
        base['special_cases'] = []
        old = calculate(base, '2026-10', 500000, full_month_confirmed=True, rule_version=FULL_RULE_VERSION)
        self.assertEqual(result['rule_version'], FACTOR_RULE_VERSION)
        self.assertEqual(result['rules_sha256'], FACTOR_RULES_SHA256)
        self.assertEqual(result['scope'], 'regular_standard_factor_monthly')
        self.assertEqual(result['individual_wage_tax_minor'], 58908)
        self.assertEqual(result['employee_social_total_minor'], 108750)
        self.assertEqual(result['net_minor'], 332342)
        self.assertEqual(result['tax_parameters']['tax_factor'], '0.753')
        self.assertTrue(result['payroll_calculation_complete'])
        self.assertFalse(result['official_system_approval'])
        for key in ('employee_contributions', 'employer_contributions', 'employer_levies',
                    'employer_total_excluding_accident_insurance_minor'):
            self.assertEqual(result[key], old[key])
        self.assertEqual(calculate(p, '2026-10', 500000, full_month_confirmed=True,
                                  rule_version=FACTOR_RULE_VERSION), result)

    def test_church_tax_uses_factored_assessment_with_state_rate(self):
        for state, expected in (('HE', 5301), ('BY', 4712)):
            p = factor_profile(); p.update(church_tax='standard', federal_state=state)
            result = calculate(p, '2026-10', 500000, full_month_confirmed=True)
            self.assertEqual(result['tax_parameters']['church_assessment_minor'], 58908)
            self.assertEqual(result['church_tax_minor'], expected)
            self.assertEqual(result['net_minor'], 332342 - expected)

    def test_incomplete_factor_or_mixed_scope_cannot_default_to_old_rules(self):
        p = factor_profile()
        changes = [dict(tax_factor=x) for x in (None, 0.753, '0.75', '1.000')]
        changes += [dict(tax_class=1), dict(tax_allowance_monthly_minor=1),
                    dict(tax_addition_monthly_minor=1), dict(special_cases=[]),
                    dict(employment_kind='minijob')]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(Problem):
                normalize_profile(dict(p, **change))
        for old in (RULE_VERSION, FULL_RULE_VERSION, 'unknown'):
            with self.subTest(rule=old), self.assertRaises(Problem):
                calculate(p, '2026-10', 500000, full_month_confirmed=True, rule_version=old)
        plain = {k:v for k,v in p.items() if k != 'tax_factor'}
        with self.assertRaises(Problem):
            calculate(plain, '2026-10', 500000, full_month_confirmed=True,
                      rule_version=FACTOR_RULE_VERSION)

    def test_remaining_scope_and_source_blockers_still_prevent_net_result(self):
        cases = [dict(month='2027-01'), dict(full_month_confirmed=False),
                 dict(source_issues=['wage_source_mismatch']), dict(gross_minor=150000),
                 dict(profile_change={'special_cases':['tax_factor','one_off_payment']}),
                 dict(profile_change={'health_insurance':'private'}),
                 dict(profile_change={'effective_from':'2026-10-02'})]
        for case in cases:
            p = factor_profile(); p.update(case.get('profile_change', {}))
            with self.subTest(case=case):
                result = calculate(p, case.get('month', '2026-10'), case.get('gross_minor', 500000),
                    full_month_confirmed=case.get('full_month_confirmed', True),
                    source_issues=case.get('source_issues', ()))
                self.assertEqual(result['rule_version'], FACTOR_RULE_VERSION)
                self.assertFalse(result['payroll_calculation_complete'])
                self.assertFalse(result['social_contributions_available'])
                self.assertIsNone(result['net_minor'])
                self.assertTrue(result['blockers'])

    def test_legacy_factor_flag_without_actual_factor_remains_blocked(self):
        p = factor_profile(); del p['tax_factor']
        result = calculate(p, '2026-10', 500000, full_month_confirmed=True)
        self.assertEqual(result['rule_version'], FULL_RULE_VERSION)
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertIsNone(result['net_minor'])
        self.assertIn('special_case:tax_factor', [b['code'] for b in result['blockers']])


if __name__ == '__main__':
    unittest.main()
