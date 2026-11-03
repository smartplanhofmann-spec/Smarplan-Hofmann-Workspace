"""Independent entitlement boundaries; expected figures are not kernel outputs.

Sources reviewed separately on 2026-11-03: EntgFG3/4, BUrlG11 and AOK
duration of continued remuneration (updated 2026-06-29). Source/UI integration
is a separate layer; these cases exercise the deterministic components only.
"""
from copy import deepcopy
from datetime import date, timedelta
import unittest

from core import Problem
from payroll_entitlements_2026 import (derive_sickness_entitlement,
    derive_unpaid_continuation, calculate_regular_absence_pay,
    calculate_vacation_reference, build_entitlement_plan)

REF = dict(id='1'*32, revision=1, content_hash='2'*64)


def illness(identity, first, last, group='a', **changes):
    return dict(id=identity*32, **{'from': first, 'to': last}, onset='before_work',
                first_scheduled_day=None, continuation_group=group*32,
                recovery_before=True, unculpable=True, evidence_refs=[REF]) | changes


def history(*episodes, start='2024-01-01'):
    return dict(employment_from=start, employment_to=None, pay_basis='monthly',
                complete_from=start, complete_through='2026-12-31',
                history_evidence_refs=[REF], episodes=list(episodes))


class EntitlementIndependentReview(unittest.TestCase):
    def test_completed_six_month_gap_restarts_twelve_month_anchor(self):
        # Independently read AOK "Neue 12-Monats-Frist" dates; not generated.
        result = derive_sickness_entitlement(history(
            illness('3', '2025-06-24', '2025-07-23'),
            illness('4', '2025-11-17', '2025-11-27'),
            illness('5', '2026-06-01', '2026-07-08')))
        self.assertEqual([30, 11, 38], [row['entitlement_calendar_days'] for row in result['episodes']])
        current = result['episodes'][-1]
        self.assertEqual('six_months_without_same_illness', current['reset_reason'])
        self.assertEqual('2026-06-01', current['twelve_month_anchor'])
        self.assertEqual(4, current['remaining_days'])

    def test_six_month_backward_boundary_at_short_february(self):
        # Previous illness ends Aug31. Feb28 still includes prior illness;
        # Mar1 follows six full illness-free calendar months Sep..Feb.
        previous = illness('3', '2025-07-21', '2025-08-31')
        before = derive_sickness_entitlement(history(previous,
            illness('4', '2026-02-28', '2026-03-05')))['episodes'][-1]
        after = derive_sickness_entitlement(history(previous,
            illness('4', '2026-03-01', '2026-03-06')))['episodes'][-1]
        self.assertEqual(0, before['entitlement_calendar_days'])
        self.assertEqual(6, after['entitlement_calendar_days'])
        self.assertEqual('six_months_without_same_illness', after['reset_reason'])

    def test_waiting_period_consumes_no_six_week_entitlement(self):
        result = derive_sickness_entitlement(history(
            illness('3', '2026-01-01', '2026-01-28'),
            illness('4', '2026-01-29', '2026-03-11'), start='2026-01-01'))
        self.assertEqual([0, 42], [row['entitlement_calendar_days'] for row in result['episodes']])
        self.assertEqual('2026-03-11', result['episodes'][1]['entitlement_to'])
        self.assertIsNone(result['episodes'][0]['entitlement_from'])

    def test_different_proven_cause_gets_own_entitlement_without_resetting_old_cause(self):
        result = derive_sickness_entitlement(history(
            illness('3', '2026-04-01', '2026-05-12'),
            illness('4', '2026-05-15', '2026-06-25', group='b'),
            illness('5', '2026-06-28', '2026-07-10')))
        self.assertEqual([42, 42, 0], [row['entitlement_calendar_days'] for row in result['episodes']])

    def test_unresolved_recovery_or_fault_never_becomes_a_new_entitlement(self):
        for field in ('recovery_before', 'unculpable'):
            source = history(illness('3', '2026-04-01', '2026-05-12'))
            source['episodes'][0][field] = False
            with self.subTest(field=field), self.assertRaises(Problem):
                derive_sickness_entitlement(source)

    def test_unpaid_month_at_january_end_has_twenty_nine_actual_days(self):
        source = dict(**{'from': '2026-01-31', 'to': '2026-03-02'}, employment_to=None,
            employment_continues=True, no_wage_claim=True, intervening_paid_days=[],
            evidence_refs=[REF], exceptions=[])
        result = derive_unpaid_continuation(source)
        self.assertEqual('2026-02-28', result['continuation_windows'][0]['statutory_deadline'])
        self.assertEqual([29, 2], [row['calendar_days'] for row in result['intervals']])
        self.assertEqual([True, False], [row['employment_for_contributions_continues'] for row in result['intervals']])
        self.assertFalse(result['tax_lzz_reduced_by_unpaid_days'])

    def test_three_day_workweek_vacation_uses_full_reference_and_rounds_once(self):
        first = date(2026, 10, 6)
        days = []
        for i in range(91):
            current = first-timedelta(days=91-i)
            works = current.weekday() in (1, 3, 5)
            days.append(dict(date=current.isoformat(), contractual_workday=works,
                base_earnings_minor=10001 if works else 0, overtime_earnings_minor=0,
                protected_reduction_minor=0, permanent_raise_minor=0, evidence_refs=[REF]))
        next(row for row in days if row['contractual_workday'])['base_earnings_minor'] += 10
        source = dict(vacation_from='2026-10-06', vacation_to='2026-10-10',
            reference_days=days, vacation_days=[dict(date=day, scheduled_regular_seconds=21600,
                evidence_refs=[REF]) for day in ('2026-10-06', '2026-10-08', '2026-10-10')],
            in_kind_daily_minor=199, evidence_refs=[REF])
        before = deepcopy(source)
        result = calculate_vacation_reference(source)
        # 39*10001+10 = 390049; /39*3 =30003.769..., plus3*199 =30601.
        self.assertEqual(dict(numerator=390049, denominator=39), result['workday_average'])
        self.assertEqual(30601, result['gross_minor'])
        self.assertEqual(64800, result['paid_absence_seconds'])
        self.assertEqual(source, before)
        self.assertFalse(result['actual_project_time_modified'])

    def test_holiday_requires_independent_entitlement_and_causation(self):
        source = dict(kind='public_holiday', hourly_rate_minor=1927, evidence_refs=[REF],
            days=[dict(date='2026-05-01', scheduled_regular_seconds=27000,
                worked_regular_seconds=0, entitled=True, absence_is_only_cause=True,
                holiday_adjacent_unexcused=False, evidence_refs=[REF])])
        self.assertEqual(14453, calculate_regular_absence_pay(source)['gross_minor'])
        for key in ('entitled', 'absence_is_only_cause'):
            denied = deepcopy(source); denied['days'][0][key] = False
            self.assertEqual(0, calculate_regular_absence_pay(denied)['gross_minor'])
        bad = deepcopy(source); bad['days'][0]['worked_regular_seconds'] = 3600
        with self.assertRaises(Problem): calculate_regular_absence_pay(bad)

    def test_unknown_historical_rule_never_falls_back_to_current(self):
        with self.assertRaises(Problem):
            build_entitlement_plan({}, rule_version='de_2026_entitlements_missing')


if __name__ == '__main__':
    unittest.main()
