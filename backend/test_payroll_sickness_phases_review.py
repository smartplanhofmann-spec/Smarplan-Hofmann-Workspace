"""Independent phase review against GKV section6 and TK examples17--19.

GKV examples are shifted from 1998/1999 to non-leap 2025/2026. No obsolete
1998 wage-rate rule is applied. All expected periods are literal dates/counts.
"""
from copy import deepcopy
import unittest

from core import Problem
from payroll_sickness_phases_2026 import derive_sickness_phases as calculate
from test_payroll_sickness_phases_2026 import history,joined
from test_payroll_entitlements_2026 import episode


class SicknessPhasesIndependentReview(unittest.TestCase):
    def gkv_first_case(self,first_end='2025-10-02'):
        return [episode('2025-09-03',first_end),
                joined('2025-09-18','2025-11-10',identity='e',group='f')]

    def test_gkv_a_and_b_one_day_changes_six_month_reset(self):
        for first_end,paid,last,reset in [
                ('2025-10-02',12,'2026-04-13','same_illness_remaining_entitlement'),
                ('2025-10-01',42,'2026-05-13','six_months_without_same_illness')]:
            plan=calculate(history(self.gkv_first_case(first_end),
                [episode('2026-04-02','2026-05-31',identity='a')]))
            row=plan['episodes'][-1]
            self.assertEqual((row['entitlement_calendar_days'],row['entitlement_to'],row['reset_reason']),(paid,last,reset))

    def test_gkv_c_added_cause_retains_only_paid_responsible_days(self):
        plan=calculate(history(self.gkv_first_case(),
            [episode('2026-04-16','2026-06-30',identity='a',group='f')]))
        self.assertEqual([30,12,30],[r['entitlement_calendar_days'] for r in plan['episodes']])
        self.assertEqual(('2025-10-03','2026-05-15'),
                         (plan['episodes'][1]['twelve_month_anchor'],plan['episodes'][2]['entitlement_to']))

    def test_gkv_d_six_month_clock_uses_end_of_au_not_end_of_payment(self):
        for begin,count in [('2026-05-10',30),('2026-05-11',42)]:
            plan=calculate(history(self.gkv_first_case(),
                [episode(begin,'2026-06-30',identity='a',group='f')]))
            self.assertEqual(plan['episodes'][-1]['entitlement_calendar_days'],count)

    def test_tk_19_published_thirteen_days_then_one_unused_day(self):
        plan=calculate(history([episode('2026-01-05','2026-02-01')],
            [episode('2026-04-10','2026-05-08',identity='e',group='f'),
             joined('2026-05-01','2026-06-30',identity='a')],
            [episode('2026-07-15','2026-08-10',identity='b')]))
        self.assertEqual([28,29,13,1],[r['entitlement_calendar_days'] for r in plan['episodes']])
        self.assertEqual('2026-07-15',plan['episodes'][-1]['entitlement_to'])

    def test_added_cause_on_final_available_day_has_one_day_and_new_anchor(self):
        plan=calculate(history([episode('2026-01-01','2026-02-04')],
            [episode('2026-04-01','2026-04-06',identity='a'),
             joined('2026-04-05','2026-05-20',identity='e',group='f')],
            [episode('2026-06-01','2026-07-31',identity='b',group='f')]))
        self.assertEqual([35,6,1,41],[r['entitlement_calendar_days'] for r in plan['episodes']])
        self.assertEqual('2026-04-07',plan['episodes'][2]['twelve_month_anchor'])

    def test_added_cause_one_day_later_has_no_anchor_or_prior_usage(self):
        plan=calculate(history([episode('2026-01-01','2026-02-04')],
            [episode('2026-04-01','2026-04-07',identity='a'),
             joined('2026-04-05','2026-05-20',identity='e',group='f')],
            [episode('2026-06-01','2026-07-31',identity='b',group='f')]))
        self.assertEqual([35,7,0,42],[r['entitlement_calendar_days'] for r in plan['episodes']])
        self.assertIsNone(plan['episodes'][2]['twelve_month_anchor'])
        self.assertEqual('2026-06-01',plan['episodes'][3]['twelve_month_anchor'])

    def test_three_actual_causes_keep_one_case_cap_and_separate_later_recurrence(self):
        plan=calculate(history([
            episode('2026-01-01','2026-01-10'),
            joined('2026-01-05','2026-01-20',identity='e',group='f'),
            joined('2026-01-15','2026-03-15',identity='a',group='b')],
            [episode('2026-06-01','2026-07-31',identity='c',group='b')]))
        self.assertEqual([10,10,22,20],[r['entitlement_calendar_days'] for r in plan['episodes']])
        self.assertEqual('2026-02-11',plan['prevention_cases'][0]['statutory_deadline'])
        self.assertEqual('2026-06-20',plan['episodes'][-1]['entitlement_to'])
        self.assertEqual(42,plan['prevention_cases'][0]['entitlement_calendar_days'])

    def test_during_work_start_with_three_day_remainder_keeps_ordinary_first_day_separate(self):
        plan=calculate(history([episode('2026-01-01','2026-02-08')],
            [episode('2026-05-01','2026-05-03',identity='a',onset='during_work'),
             joined('2026-05-02','2026-05-30',identity='e',group='f')],pay_basis='hourly'))
        self.assertEqual([39,2,1],[r['entitlement_calendar_days'] for r in plan['episodes']])
        self.assertEqual(('2026-05-01','2026-05-04'),
            (plan['episodes'][1]['first_day_remaining_regular_wage'],plan['prevention_cases'][1]['statutory_deadline']))

    def test_adjacent_new_certificate_needs_explicit_recovery_evidence_and_no_mutation(self):
        source=history([episode('2026-04-01','2026-04-20')],
                       [episode('2026-04-21','2026-05-30',identity='e',group='f')])
        original=deepcopy(source);plan=calculate(source)
        self.assertEqual([20,40],[r['entitlement_calendar_days'] for r in plan['episodes']])
        self.assertEqual(source,original)
        source['episodes'][1]['recovery_before']=False
        with self.assertRaises(Problem):calculate(source)


if __name__=='__main__':unittest.main()
