"""Independent exact-cent arithmetic and evidence boundaries for travel tax."""
from copy import deepcopy
import unittest

from core import Problem
from payroll_travel_tax_2026 import calculate_flat_travel_tax

REF = dict(id='a'*32, revision=1, content_hash='b'*64)


def evidence(**changes):
    return dict(policy_ref=REF, filing_period_from='2026-11-01', filing_period_to='2026-11-30',
        payroll_month='2026-11', taxation_recorded_on='2026-11-03', tax_certificate_issued_on=None,
        eligible_limit_minor=1400, eligible_source_refs=[REF], church_rate_region='standard',
        church_method_applies_to_all=True, church_membership_evidence=None,
        employee_deduction_authorization=None) | changes


def calculate(amount=1400, **changes):
    return calculate_flat_travel_tax(amount, **(dict(federal_state='BW', church_tax=False,
        church_method='simplified', employer_bears_tax=True, evidence=evidence()) | changes))


class TravelFlatTaxTests(unittest.TestCase):
    def test_bw_simplified_also_taxes_nonmembers_and_rounds_each_tax_down(self):
        result = calculate()
        # 14*25%=3.50; 3.50*5.5%=0.1925; 3.50*4.5%=0.1575.
        self.assertEqual((350, 19, 15, 384, 0, 1400), tuple(result[key] for key in
            ('wage_tax_minor', 'solidarity_minor', 'church_tax_minor',
             'employer_total_minor', 'employee_tax_minor', 'employee_cash_after_flat_tax_minor')))
        self.assertTrue(result['social_exempt'])
        self.assertEqual(0, result['social_gross_minor'])
        self.assertFalse(result['actual_payment_created'])
        self.assertFalse(result['statutory_transmitted'])
        self.assertEqual(15, calculate(church_tax=True)['church_tax_minor'])
        self.assertEqual(15, calculate(church_tax=None)['church_tax_minor'])

    def test_fractional_cent_wage_tax_is_not_commercially_rounded(self):
        result = calculate(1403, evidence=evidence(eligible_limit_minor=1403))
        self.assertEqual((350, 19, 15), tuple(result[k] for k in
                         ('wage_tax_minor', 'solidarity_minor', 'church_tax_minor')))
        self.assertEqual(0, calculate(3)['wage_tax_minor'])
        self.assertEqual(1, calculate(4)['wage_tax_minor'])

    def test_proven_nonmembership_and_membership_use_different_evidenced_method(self):
        proof = dict(kind='elstam', reference=REF)
        free = calculate(church_method='evidence', evidence=evidence(church_membership_evidence=proof))
        self.assertEqual(0, free['church_tax_minor'])
        member = calculate(church_method='evidence', church_tax=True,
                           evidence=evidence(church_membership_evidence=proof))
        self.assertEqual((28, 397), (member['church_tax_minor'], member['statutory_employer_due_minor']))
        absent = calculate(church_method='evidence')
        self.assertFalse(absent['can_calculate'])
        self.assertIsNone(absent['church_tax_minor'])
        self.assertIn('travel_church_membership_missing', [b['code'] for b in absent['blockers']])

    def test_all_state_simplified_rates_and_explicit_regional_exceptions(self):
        # 100 EUR extra meals ->25 EUR LSt. Values are direct products of the
        # separately read rate table, not outputs captured from this function.
        expected = dict(BW=112, BY=175, BE=125, BB=125, HB=175, HH=100,
            HE=175, MV=125, NI=150, NW=175, RP=175, SL=175, SN=125, ST=125, SH=150, TH=125)
        for state, church in expected.items():
            with self.subTest(state=state):
                self.assertEqual(church, calculate(10000, federal_state=state,
                    evidence=evidence(eligible_limit_minor=10000))['church_tax_minor'])
        self.assertEqual(24, calculate(federal_state='NI',
            evidence=evidence(church_rate_region='ni_ev_westfalen'))['church_tax_minor'])
        self.assertEqual(31, calculate(church_method='evidence', church_tax=True,
            evidence=evidence(church_rate_region='bw_bad_wimpfen_mainz',
                              church_membership_evidence=dict(kind='substitute_tax_certificate', reference=REF)))['church_tax_minor'])
        with self.assertRaises(Problem): calculate(evidence=evidence(church_rate_region='ni_ev_westfalen'))

    def test_policy_is_uniform_within_filing_period_and_not_person_selected(self):
        left, right = calculate(church_tax=True), calculate(church_tax=False)
        self.assertEqual(left['policy_key'], right['policy_key'])
        self.assertEqual(left['policy_choice_hash'], right['policy_choice_hash'])
        other = calculate(church_method='evidence', evidence=evidence(
            church_membership_evidence=dict(kind='elstam', reference=REF)))
        self.assertEqual(left['policy_key'], other['policy_key'])
        self.assertNotEqual(left['policy_choice_hash'], other['policy_choice_hash'])
        self.assertFalse(calculate(evidence=evidence(church_method_applies_to_all=False))['can_calculate'])

    def test_timely_taxation_and_social_exemption_are_separate_from_flat_tax_amount(self):
        at = calculate(evidence=evidence(taxation_recorded_on='2027-02-28'))
        late = calculate(evidence=evidence(taxation_recorded_on='2027-03-01'))
        self.assertTrue(at['social_exempt'])
        self.assertFalse(late['social_exempt'])
        self.assertEqual(1400, late['social_gross_minor'])
        self.assertEqual(at['statutory_employer_due_minor'], late['statutory_employer_due_minor'])
        prior_certificate = calculate(evidence=evidence(tax_certificate_issued_on='2026-11-02'))
        self.assertFalse(prior_certificate['social_exempt'])
        missing = calculate(evidence=evidence(taxation_recorded_on=None))
        self.assertFalse(missing['can_calculate'])
        self.assertIsNone(missing['social_gross_minor'])

    def test_evidenced_employee_cost_transfer_does_not_change_statutory_employer_debt(self):
        missing = calculate(employer_bears_tax=False)
        self.assertFalse(missing['can_calculate'])
        result = calculate(employer_bears_tax=False, evidence=evidence(employee_deduction_authorization=REF))
        self.assertEqual((384, 0, 384, 1016), tuple(result[key] for key in
            ('statutory_employer_due_minor', 'employer_total_minor',
             'employee_tax_minor', 'employee_cash_after_flat_tax_minor')))
        self.assertTrue(result['social_exempt'])

    def test_real_travel_capacity_cannot_be_silently_capped_or_reused(self):
        result = calculate(1401)
        self.assertFalse(result['can_calculate'])
        self.assertIsNone(result['wage_tax_minor'])
        self.assertIn('travel_flat_capacity_exceeded', [b['code'] for b in result['blockers']])
        with self.assertRaises(Problem): calculate(evidence=evidence(eligible_source_refs=[REF, REF]))

    def test_filing_period_is_month_quarter_or_year_and_contains_actual_payroll(self):
        for first, last in [('2026-10-01', '2026-12-31'), ('2026-01-01', '2026-12-31')]:
            self.assertTrue(calculate(evidence=evidence(filing_period_from=first, filing_period_to=last))['can_calculate'])
        for change in [dict(filing_period_to='2026-11-29'), dict(payroll_month='2026-10'),
                       dict(taxation_recorded_on='2026-10-31'), dict(filing_period_from='2025-11-01')]:
            with self.subTest(change=change), self.assertRaises(Problem): calculate(evidence=evidence(**change))

    def test_exact_types_source_binding_and_no_mutation(self):
        value = evidence(); before = deepcopy(value)
        original = calculate(evidence=value)
        self.assertEqual(value, before)
        revised = calculate(evidence=evidence(policy_ref=dict(REF, revision=2)))
        self.assertEqual(original['statutory_employer_due_minor'], revised['statutory_employer_due_minor'])
        self.assertNotEqual(original['source_hash'], revised['source_hash'])
        for value in (True, 14.0, -1, '1400'):
            with self.subTest(value=value), self.assertRaises(Problem): calculate(value)
        for extra in [dict(evidence=evidence(desired_tax_minor=0)), dict(church_tax=0),
                      dict(employer_bears_tax=1), dict(federal_state='DE')]:
            with self.subTest(extra=extra), self.assertRaises(Problem): calculate(**extra)


if __name__ == '__main__':
    unittest.main()
