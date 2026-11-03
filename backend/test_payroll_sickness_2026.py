"""Published IKK2026 dates and independently calculated v2 boundaries."""
from copy import deepcopy
import hashlib
import unittest

from core import Problem, canonical
import payroll_entitlements_2026 as v1
from payroll_sickness_2026 import derive_sickness_entitlement, SICKNESS_RULE_VERSION
from payroll_entitlement_dispatch import build_entitlement_plan
from test_payroll_entitlements_2026 import episode, sickness


class SicknessV2Tests(unittest.TestCase):
    def test_published_ikk_saturday_hourly_starts_sunday_not_monday_shift(self):
        source=sickness(episode('2026-08-01','2026-10-01',onset='non_workday',
            scheduled='2026-08-03'),pay_basis='hourly')
        before=deepcopy(source)
        row=derive_sickness_entitlement(source)['episodes'][0]
        self.assertEqual(('2026-08-02','2026-08-02','2026-09-12',42),tuple(row[key] for key in
            ('count_from','entitlement_from','entitlement_to','entitlement_calendar_days')))
        self.assertEqual(source,before)
        self.assertEqual('2026-09-13',v1.derive_sickness_entitlement(source)['episodes'][0]['entitlement_to'])

    def test_published_ikk_monthly_saturday_counts_first_day(self):
        row=derive_sickness_entitlement(sickness(episode('2026-08-01','2026-10-01',onset='non_workday')))['episodes'][0]
        self.assertEqual(('2026-08-01','2026-09-11',42),tuple(row[key] for key in
            ('count_from','entitlement_to','entitlement_calendar_days')))

    def test_later_shift_does_not_extend_calendar_entitlement(self):
        for scheduled in ('2026-08-03','2026-08-05','2026-08-10'):
            row=derive_sickness_entitlement(sickness(episode('2026-08-01','2026-10-01',onset='non_workday',
                scheduled=scheduled),pay_basis='hourly'))['episodes'][0]
            self.assertEqual('2026-09-12',row['entitlement_to'])
        with self.assertRaises(Problem):
            derive_sickness_entitlement(sickness(episode('2026-08-01','2026-10-01',onset='non_workday',
                scheduled='2026-08-01'),pay_basis='hourly'))

    def test_recurrence_consumes_calendar_days_before_later_shift(self):
        source=sickness(episode('2026-08-01','2026-08-10',onset='non_workday',scheduled='2026-08-03'),
            episode('2026-08-17','2026-10-01',identity='e'),pay_basis='hourly')
        left,right=derive_sickness_entitlement(source)['episodes']
        self.assertEqual((9,33,'2026-09-18'),(left['entitlement_calendar_days'],right['entitlement_calendar_days'],right['entitlement_to']))
        self.assertEqual(9,right['prior_used_days'])

    def test_waiting_period_still_defers_pay_without_consuming_six_weeks(self):
        source=sickness(episode('2026-08-01','2026-10-01',onset='non_workday',
            scheduled='2026-08-03'),start='2026-07-15',pay_basis='hourly')
        row=derive_sickness_entitlement(source)['episodes'][0]
        self.assertEqual(('2026-08-02','2026-08-11','2026-08-12','2026-09-22',42),tuple(row[key] for key in
            ('count_from','waiting_period_end','entitlement_from','entitlement_to','entitlement_calendar_days')))

    def test_during_work_retains_separate_first_day_wage_and_ordinary_boundaries(self):
        row=derive_sickness_entitlement(sickness(episode('2026-08-03','2026-10-01',onset='during_work'),pay_basis='hourly'))['episodes'][0]
        self.assertEqual(('2026-08-04','2026-09-14','2026-08-03'),tuple(row[key] for key in
            ('count_from','entitlement_to','first_day_remaining_regular_wage')))

    def test_dispatch_preserves_v1_outputs_and_rejects_unknown_or_wrong_kind(self):
        source=sickness(episode('2026-08-01','2026-10-01',onset='non_workday',scheduled='2026-08-03'),pay_basis='hourly')
        snapshot=dict(schema_version=1,kind='sickness_history',details=dict(input=source))
        legacy=v1.build_entitlement_plan(snapshot)
        self.assertEqual(legacy,build_entitlement_plan(snapshot,v1.ENTITLEMENT_RULE_VERSION))
        current=build_entitlement_plan(snapshot)
        self.assertEqual(SICKNESS_RULE_VERSION,current['rule_version'])
        self.assertNotEqual(legacy['plan_hash'],current['plan_hash'])
        self.assertEqual(legacy['input_hash'],current['input_hash'])
        self.assertEqual(legacy['source_hash'],current['source_hash'])
        for rule in ('de_2026_sickness_v3',True,None):
            bad=dict(snapshot,kind='regular_absence')
            with self.assertRaises(Problem):build_entitlement_plan(bad,SICKNESS_RULE_VERSION if rule is None else rule)
        with self.assertRaises(Problem):build_entitlement_plan(dict(snapshot,schema_version=True))

    def test_rule_and_hashes_bind_original_later_shift_even_when_amount_dates_equal(self):
        source=sickness(episode('2026-08-01','2026-10-01',onset='non_workday',scheduled='2026-08-03'),pay_basis='hourly')
        earlier=derive_sickness_entitlement(source)
        source['episodes'][0]['first_scheduled_day']='2026-08-05'
        later=derive_sickness_entitlement(source)
        self.assertEqual(earlier['episodes'],later['episodes'])
        self.assertNotEqual(earlier['source_hash'],later['source_hash'])
        self.assertEqual(hashlib.sha256(canonical({key:value for key,value in later.items() if key!='plan_hash'}).encode()).hexdigest(),later['plan_hash'])


if __name__=='__main__':unittest.main()
