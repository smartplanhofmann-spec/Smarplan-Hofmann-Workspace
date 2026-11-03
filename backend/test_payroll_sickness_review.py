"""Independent v2 calendar/recurrence checks after reading IKK2026 p8."""
from copy import deepcopy
import unittest

from core import Problem
import payroll_entitlements_2026 as historical
from payroll_entitlement_dispatch import build_entitlement_plan
from payroll_sickness_2026 import derive_sickness_entitlement, SICKNESS_RULE_VERSION
from test_payroll_entitlements_2026 import episode, sickness


class IndependentSicknessReview(unittest.TestCase):
    def test_free_saturday_before_short_february_does_not_wait_for_next_shift(self):
        value=sickness(episode('2026-01-31','2026-04-01',onset='non_workday',
                               scheduled='2026-02-10'),pay_basis='hourly')
        before=deepcopy(value);row=derive_sickness_entitlement(value)['episodes'][0]
        self.assertEqual(('2026-02-01','2026-03-14',42),tuple(row[key] for key in
            ('entitlement_from','entitlement_to','entitlement_calendar_days')))
        self.assertEqual(value,before)
        self.assertEqual('2026-02-10',value['episodes'][0]['first_scheduled_day'])

    def test_calendar_days_before_first_shift_reduce_actual_same_illness_remainder(self):
        value=sickness(episode('2026-01-31','2026-02-02',onset='non_workday',scheduled='2026-02-02'),
            episode('2026-03-02','2026-05-01',identity='e'),pay_basis='hourly')
        first,second=derive_sickness_entitlement(value)['episodes']
        self.assertEqual((2,2,40,'2026-04-10'),(first['entitlement_calendar_days'],
            second['prior_used_days'],second['entitlement_calendar_days'],second['entitlement_to']))

    def test_same_facts_keep_explicit_historical_rule_and_new_rule_separate(self):
        value=sickness(episode('2026-01-31','2026-04-01',onset='non_workday',
                               scheduled='2026-02-02'),pay_basis='hourly')
        snapshot=dict(schema_version=1,kind='sickness_history',details=dict(input=value))
        old=build_entitlement_plan(snapshot,historical.ENTITLEMENT_RULE_VERSION)
        new=build_entitlement_plan(snapshot,SICKNESS_RULE_VERSION)
        self.assertEqual(old,historical.build_entitlement_plan(snapshot))
        self.assertEqual(('2026-03-15','2026-03-14'),
            (old['episodes'][0]['entitlement_to'],new['episodes'][0]['entitlement_to']))
        self.assertEqual(old['input_hash'],new['input_hash'])
        self.assertNotEqual(old['plan_hash'],new['plan_hash'])
        with self.assertRaises(Problem):build_entitlement_plan(snapshot,'newest')

    def test_existing_six_month_reset_keeps_new_anchor_for_later_recurrence(self):
        value=sickness(episode('2025-01-01','2025-02-11'),
            episode('2025-08-12','2025-09-22',identity='e'),
            episode('2026-01-02','2026-02-01',identity='f'),
            start='2024-01-01',complete_from='2024-01-01')
        first,reset,again=derive_sickness_entitlement(value)['episodes']
        self.assertEqual(42,first['entitlement_calendar_days'])
        self.assertEqual(('six_months_without_same_illness','2025-08-12',42),
            (reset['reset_reason'],reset['twelve_month_anchor'],reset['entitlement_calendar_days']))
        self.assertEqual(('same_illness_remaining_entitlement',0,None),
            (again['reset_reason'],again['entitlement_calendar_days'],again['entitlement_to']))

    def test_waiting_period_does_not_consume_the_42_calendar_days(self):
        value=sickness(episode('2026-06-15','2026-08-21'),
                       start='2026-06-01',pay_basis='hourly')
        row=derive_sickness_entitlement(value)['episodes'][0]
        self.assertEqual(('2026-06-29','2026-08-09',42),tuple(row[key] for key in
            ('entitlement_from','entitlement_to','entitlement_calendar_days')))


if __name__=='__main__':
    unittest.main()
