"""Independent monetary and March-clause checks over accepted private sources.

The shared builder supplies real private receipts only; expected money is hand
calculated from 17 SV days, actual pay and the published 2025/2026 parameters.
"""
from copy import deepcopy
import unittest
from core import Problem
import test_payroll_oneoff_composition_2026 as fixtures
from payroll_oneoff_composition_2026 import calculate_oneoff_source, ONEOFF_RULE_VERSION


def calculate(source):
    return calculate_oneoff_source(source, rule_version=ONEOFF_RULE_VERSION, source_contract_version=1)


class OneOffCompositionIndependentReview(unittest.TestCase):
    def setUp(self):
        self.builder = fixtures.OneoffCompositionTests('runTest')
        self.builder.setUp()
        self.addCleanup(self.builder.doCleanups)

    def test_exact_current_health_room_keeps_whole_bonus_in_receipt_year(self):
        # January15–31:17days. KV cap6975000*17/360=329375;
        # running pay round(300000*17/31)=164516 -> room164859.
        # Permitted separate PV rounding: round2967.462 + round989.154=3956
        # (GKV31.03.2025, section3.3, printedpage12), not combined3957.
        source = self.builder.source(january=True, bonus=164859, previous=True)
        result = calculate(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        assignment = result['one_off_details']['assignment']
        self.assertEqual((2026, False, '2026-01-31'),
            (assignment['social_year'], assignment['march_clause'], assignment['assigned_period_end']))
        self.assertEqual(dict(health=164859, care=164859, pension=164859, unemployment=164859), assignment['bases_minor'])
        self.assertEqual(result['one_off_details']['social']['employee_contributions'],
            dict(health_general=12035, health_additional=2390, pension=15332, unemployment=2143, care=3956))

    def test_one_cent_over_health_room_assigns_entire_payment_to_actual_prior_year(self):
        source = self.builder.source(january=True, bonus=164860, previous=True)
        result = calculate(source)
        self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
        extra = result['one_off_details']
        self.assertEqual((2026, 2025, True), (extra['assignment']['tax_year'], extra['assignment']['social_year'], extra['assignment']['march_clause']))
        self.assertEqual(dict(health=164860, care=164860, pension=164860, unemployment=164860), extra['assignment']['bases_minor'])
        # Historical1.1% Zusatz, Saxony, second-child discount:
        # KV12035+907,RV15332,AV2143,PV round3791.78-round412.15=3380.
        self.assertEqual(dict(health_general=12035, health_additional=907, pension=15332, unemployment=2143, care=3380), extra['social']['employee_contributions'])
        self.assertEqual(33797, extra['social']['employee_total_minor'])
        self.assertEqual(2143, extra['social']['employer_contributions']['care'])
        self.assertEqual(dict(u1=0, u2=0, insolvency=247), extra['social']['employer_levies'])

    def test_bonus_above_distinct_caps_preserves_actual_running_pay_and_cash_identity(self):
        source = self.builder.source(bonus=500000)
        original = deepcopy(source)
        result = calculate(source)
        extra = result['one_off_details']; running = result['running_calculation']
        # RV cap10140000*17/360=478833.333 ->478833; minus164516.
        self.assertEqual(dict(health=164859, care=164859, pension=314317, unemployment=314317), extra['assignment']['bases_minor'])
        self.assertEqual(dict(health_general=12035, health_additional=2390, pension=29231, unemployment=4086, care=3956), extra['social']['employee_contributions'])
        self.assertEqual((164516, 664516), (running['gross_minor'], result['gross_minor']))
        self.assertEqual(result['gross_minor'] - result['employee_social_total_minor'] - result['employee_tax_minor'] - result['net_deductions_minor'], result['payout_minor'] - result['employee_additional_payment_minor'])
        for levy in ('u1', 'u2'):
            self.assertEqual(running['employer_levies'][levy], result['employer_levies'][levy])
        self.assertFalse(extra['actual_payment_created'])
        self.assertEqual(source, original)

    def test_source_person_and_receipt_month_cannot_be_relabelled(self):
        source = self.builder.source()
        for field, value in [('employee_id','e' * 32), ('month','2026-11')]:
            with self.subTest(field=field), self.assertRaises(Problem):
                calculate(source | {field:value})


if __name__ == '__main__':
    unittest.main()
