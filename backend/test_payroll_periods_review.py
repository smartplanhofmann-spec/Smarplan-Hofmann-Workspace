"""Independent counterexamples; source derivations are recorded in the review doc.

These expectations do not read the implementation's reference JSON or calculate
expected tax through the annual production kernel. Fixtures alone are shared.
"""
from copy import deepcopy
from fractions import Fraction
import unittest

from core import Problem
from payroll_pap_periods_2026 import calculate_period_tax, daily_tax_feature
from payroll_periods_2026 import build_period_plan, calculate_period_source
from test_payroll_periods_2026 import period_snapshot


def hourly_snapshot(*, gross, days, kind='regular', **profile):
    source = period_snapshot(month='2026-07', start='2026-07-01',
        end=f'2026-07-{days:02}', amount=gross, kind=kind,
        regular_annual_gross_minor=6000000 if kind == 'regular' else 120000,
        **profile)
    source['preparation']['snapshot']['agreements'][0]['pay_basis'] = 'hourly'
    source['preparation']['snapshot']['net_work_seconds'] = 3600
    source['preparation']['snapshot']['approved_days'] = [
        dict(date='2026-07-01', net_seconds=3600)]
    return source


class IndependentPeriodReviewTests(unittest.TestCase):
    def test_daily_remainder_and_each_component_truncation(self):
        args = dict(tax_class=1, children_half_units=0, additional_health_percent='2.90',
            saxony=False, childless_surcharge=True, care_child_discounts=0,
            church_member=True, allowance_monthly_minor=0, addition_monthly_minor=0)
        result = calculate_period_tax(gross_minor=37502, lzz=4, tax_days=3, **args)
        self.assertEqual(result['totals'], dict(LSTLZZ=4641, SOLZLZZ=0, BK=4641))
        inputs = result['inputs']
        self.assertEqual((inputs['gross_minor'], inputs['pap_gross_minor'],
            inputs['gross_remainder_minor'], inputs['gross_divisor']), (37502,12500,2,3))
        self.assertEqual(inputs['pap_gross_minor']*3+inputs['gross_remainder_minor'],37502)

    def test_monthly_feature_rounding_is_up_to_five_cents_for_both_features(self):
        for monthly, expected in ((0,0),(150,5),(151,10),(10000,335),(14999,500)):
            with self.subTest(monthly=monthly):
                self.assertEqual(daily_tax_feature(monthly), expected)
        result = calculate_period_tax(gross_minor=37500,lzz=4,tax_days=3,
            allowance_monthly_minor=10000,addition_monthly_minor=151,
            tax_class=1,children_half_units=0,additional_health_percent='2.90',
            saxony=False,childless_surcharge=True,care_child_discounts=0,church_member=False)
        self.assertEqual(result['inputs']['allowance_input_minor'],335)
        self.assertEqual(result['inputs']['addition_input_minor'],10)

    def test_bavarian_church_tax_uses_total_actual_period_measure(self):
        source = hourly_snapshot(gross=425000, days=17, federal_state='BY',
            tax_class=6, church_tax='standard')
        result = calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        self.assertEqual(result['individual_wage_tax_minor'],126922)
        self.assertEqual(result['solidarity_minor'],3655)
        self.assertEqual(result['church_tax_minor'],10153)
        self.assertNotEqual(result['church_tax_minor'],10149)
        self.assertEqual(result['employee_tax_minor'],140730)
        self.assertEqual(result['employee_contributions'],dict(health_general=24044,
            health_additional=4776,pension=39525,unemployment=5525,care=7905))
        self.assertEqual(result['employer_contributions'],dict(health_general=24044,
            health_additional=4776,pension=39525,unemployment=5525,care=5929))

    def test_one_day_minimum_is_a_rounded_assessment_then_contribution(self):
        # Derived from the separate assessment/contribution stages in example29,
        # not a published official one-day figure. No early daily minimum * days.
        source = period_snapshot(month='2026-07',start='2026-07-31',
            end='2026-07-31',amount=15000,kind='minijob')
        result = calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        self.assertEqual(result['gross_minor'],500)
        self.assertEqual(result['period_details']['social_periods'][0]['minimum_pension_basis_minor'],583)
        self.assertEqual(result['employee_contributions']['pension'],33)
        self.assertEqual(result['employer_contributions']['pension'],75)

    def test_minimum_27_day_arithmetic_does_not_copy_printed_source_error(self):
        # The source's unpaid-leave cause is a separate unsupported case. This
        # supported 27-day employment tests its arithmetic, not that full example.
        result = calculate_period_source(hourly_snapshot(gross=5000,days=27,kind='minijob'))
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        self.assertEqual(result['period_details']['social_periods'][0]['minimum_pension_basis_minor'],15750)
        self.assertEqual(result['employee_contributions']['pension'],2180)
        self.assertEqual(result['employer_contributions']['pension'],750)
        self.assertEqual(sum(result[side]['pension'] for side in
            ('employee_contributions','employer_contributions')),2930)

    def test_negative_minijob_net_retains_reimbursement_not_negative_payout(self):
        source = period_snapshot(month='2026-07',start='2026-07-31',
            end='2026-07-31',amount=30,kind='minijob')
        result = calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        self.assertEqual((result['gross_minor'],result['net_minor'],result['payout_minor'],
            result['employee_additional_payment_minor']),(1,-107,0,107))
        source['profiles'][0]['profile']['pension_other_compulsory'] = True
        exempt_minimum = calculate_period_source(source)
        self.assertEqual(exempt_minimum['employee_contributions']['pension'],0)
        self.assertEqual(exempt_minimum['payout_minor'],1)

    def test_transition_one_day_does_not_round_fictitious_monthly_basis_early(self):
        assessment = dict(status='within_transition_area',assessed_on='2026-01-01',
            regular_monthly_gross_minor=60930,forecast_months=12,
            foreseeable_one_off_payments=False,note='Independent boundary case')
        source = period_snapshot(month='2026-07',start='2026-07-31',
            end='2026-07-31',amount=60930,transition_assessment=assessment)
        result = calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        self.assertEqual(result['gross_minor'],2031)
        basis = result['period_details']['transition']
        self.assertEqual(basis['total_assessment_minor'],1354)
        self.assertEqual(basis['employee_assessment_minor'],30)
        self.assertNotEqual(basis['total_assessment_minor'],1355)

    def test_calendar_contract_ratio_is_not_replaced_by_social_days_over_30(self):
        assessment = dict(status='within_transition_area',assessed_on='2026-01-01',
            regular_monthly_gross_minor=60394,forecast_months=12,
            foreseeable_one_off_payments=False,note='Independent calendar ratio')
        source = period_snapshot(month='2026-07',start='2026-07-01',
            end='2026-07-16',amount=60394,method='calendar_days_actual',
            transition_assessment=assessment)
        result = calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        self.assertEqual(result['gross_minor'],31171)
        basis = result['period_details']['transition']
        self.assertEqual(basis['ratio'],dict(numerator=16,denominator=31))
        self.assertEqual((basis['total_assessment_minor'],basis['employee_assessment_minor']),(20656,69))
        self.assertEqual(Fraction(basis['monthly_equivalent_minor']),Fraction(966301,16))

    def test_full_february_and_thirty_actual_days_in_july_have_distinct_tax_lzz(self):
        feb = build_period_plan(period_snapshot(month='2026-02',start='2026-02-01',end='2026-02-28'))
        jul = build_period_plan(period_snapshot(month='2026-07',start='2026-07-02',end='2026-07-31'))
        self.assertEqual((feb['social_periods'][0]['days'],jul['social_periods'][0]['days']),(30,30))
        self.assertEqual((feb['tax_periods'][0]['lzz'],jul['tax_periods'][0]['lzz']),(2,4))
        self.assertEqual((feb['employment_intervals'][0]['calendar_days'],jul['employment_intervals'][0]['calendar_days']),(28,30))

    def test_required_midmonth_fund_change_is_blocked_without_fabricated_net(self):
        source = period_snapshot(month='2026-07',start='2026-07-01',end='2026-07-31')
        second = deepcopy(source['profiles'][0])
        second.update(id='8'*32,content_hash='8'*64)
        second['profile'].update(effective_from='2026-07-16',health_fund='Second synthetic fund',health_additional_percent='3.200')
        source['profiles'].append(second)
        source['case_details']['profile_refs'].append({key:second[key] for key in ('id','revision','content_hash')})
        result = calculate_period_source(source)
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertIsNone(result['net_minor'])
        self.assertIn('profile_changed_in_period',{value['code'] for value in result['blockers']})

    def test_unpaid_absence_keeps_period_days_and_requires_entitlement_branch(self):
        source = period_snapshot(month='2026-07',start='2026-07-01',end='2026-07-31')
        source['preparation']['snapshot']['approved_absences'] = [
            dict(kind='unpaid',start_date='2026-07-21',end_date='2026-07-31')]
        plan = build_period_plan(source)
        self.assertFalse(plan['can_calculate'])
        self.assertEqual(plan['social_periods'][0]['days'],30)
        self.assertEqual(plan['tax_periods'][0]['lzz'],2)
        result = calculate_period_source(source)
        self.assertIsNone(result['net_minor'])
        self.assertIn('entitlement_requires_calculation',{value['code'] for value in result['blockers']})

    def test_invalid_daily_period_discriminants_are_rejected(self):
        args = dict(gross_minor=37500,tax_days=3,allowance_monthly_minor=0,
            addition_monthly_minor=0,tax_class=1,children_half_units=0,
            additional_health_percent='2.90',saxony=False,childless_surcharge=True,
            care_child_discounts=0,church_member=False)
        for lzz in (True,1,3,'4',None):
            with self.subTest(lzz=lzz), self.assertRaises(Problem):
                calculate_period_tax(lzz=lzz,**args)


if __name__ == '__main__':
    unittest.main()
