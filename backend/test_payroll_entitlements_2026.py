"""Published 2026 EFZ dates and independent statutory entitlement boundaries."""
from copy import deepcopy
from datetime import date,timedelta
import unittest

from core import Problem
from payroll_entitlements_2026 import (calendar_month_period_end,derive_sickness_entitlement,
    derive_unpaid_continuation,calculate_regular_absence_pay,calculate_vacation_reference)
from payroll_holidays_2026 import public_holiday,STATES

REF=dict(id='a'*32,revision=1,content_hash='b'*64)


def episode(first,last,*,onset='before_work',group='c',identity='d',scheduled=None):
    return dict(id=identity*32,**{'from':first,'to':last},onset=onset,
        first_scheduled_day=scheduled,continuation_group=group*32,
        recovery_before=True,unculpable=True,evidence_refs=[REF])


def sickness(*episodes,start='2025-01-01',pay_basis='monthly',complete_from=None):
    return dict(employment_from=start,employment_to=None,pay_basis=pay_basis,
        complete_from=complete_from or start,complete_through='2026-12-31',
        history_evidence_refs=[REF],episodes=list(episodes))


def unpaid(first,last,**changes):
    return dict(**{'from':first,'to':last},employment_to=None,employment_continues=True,
        no_wage_claim=True,intervening_paid_days=[],evidence_refs=[REF],exceptions=[],**changes)


def vacation():
    first=date(2026,10,5)
    history=[]
    for i in range(91):
        current=first-timedelta(days=91-i);workday=current.weekday()<5
        history.append(dict(date=current.isoformat(),contractual_workday=workday,
            base_earnings_minor=10000 if workday else 0,overtime_earnings_minor=0,
            protected_reduction_minor=0,permanent_raise_minor=0,evidence_refs=[REF]))
    return dict(vacation_from=first.isoformat(),vacation_to='2026-10-09',
        reference_days=history,vacation_days=[dict(date=(first+timedelta(days=i)).isoformat(),
            scheduled_regular_seconds=28800,evidence_refs=[REF]) for i in range(5)],
        in_kind_daily_minor=0,evidence_refs=[REF])


class EntitlementDatesTests(unittest.TestCase):
    def test_published_aok_2026_before_work_and_during_work(self):
        # AOK 29.06.2026: 17 May before shift => 27 June;
        # onset during shift => 28 June plus ordinary wages on 17 May.
        before=derive_sickness_entitlement(sickness(episode('2026-05-17','2026-07-10')))['episodes'][0]
        self.assertEqual(('2026-05-17','2026-06-27',42),
            (before['entitlement_from'],before['entitlement_to'],before['entitlement_calendar_days']))
        during=derive_sickness_entitlement(sickness(episode('2026-05-17','2026-07-10',onset='during_work')))['episodes'][0]
        self.assertEqual(('2026-05-18','2026-06-28','2026-05-17'),
            (during['entitlement_from'],during['entitlement_to'],during['first_day_remaining_regular_wage']))

    def test_published_aok_2026_waiting_period(self):
        row=derive_sickness_entitlement(sickness(episode('2026-07-15','2026-10-01'),start='2026-07-01'))['episodes'][0]
        self.assertEqual(('2026-07-29','2026-09-08',42),
            (row['entitlement_from'],row['entitlement_to'],row['entitlement_calendar_days']))

    def test_published_recurrent_22_plus_20_days(self):
        rows=derive_sickness_entitlement(sickness(episode('2026-06-21','2026-07-12'),
            episode('2026-07-15','2026-08-15',identity='e')))['episodes']
        self.assertEqual((22,20,'2026-08-03'),
            (rows[0]['entitlement_calendar_days'],rows[1]['entitlement_calendar_days'],rows[1]['entitlement_to']))

    def test_published_six_months_reset_and_failure(self):
        yes=derive_sickness_entitlement(sickness(episode('2025-08-19','2025-10-13'),
            episode('2026-05-05','2026-05-19',identity='e')))['episodes'][-1]
        self.assertEqual(('six_months_without_same_illness',15),(yes['reset_reason'],yes['entitlement_calendar_days']))
        no=derive_sickness_entitlement(sickness(episode('2025-08-19','2025-10-03'),
            episode('2026-03-30','2026-04-13',identity='e')))['episodes'][-1]
        self.assertEqual(0,no['entitlement_calendar_days'])
        self.assertIsNone(no['entitlement_to'])

    def test_published_twelve_month_reset_only_at_new_episode(self):
        history=sickness(episode('2025-01-04','2025-01-30'),
            episode('2025-06-28','2025-07-27',identity='e'),
            episode('2025-12-20','2026-01-11',identity='f'),
            episode('2026-06-01','2026-07-08',identity='a'),start='2024-01-01')
        rows=derive_sickness_entitlement(history)['episodes']
        self.assertEqual(0,rows[2]['entitlement_calendar_days'])
        self.assertEqual(('twelve_months_since_first_case',38),(rows[3]['reset_reason'],rows[3]['entitlement_calendar_days']))
        long=derive_sickness_entitlement(sickness(episode('2025-05-01','2026-08-01')))['episodes'][0]
        self.assertEqual(42,long['entitlement_calendar_days'])

    def test_hourly_free_day_starts_at_first_evidenced_shift(self):
        row=derive_sickness_entitlement(sickness(episode('2026-05-17','2026-07-10',onset='non_workday',
            scheduled='2026-05-18'),pay_basis='hourly'))['episodes'][0]
        self.assertEqual('2026-06-28',row['entitlement_to'])

    def test_incomplete_history_and_overlap_do_not_reset_entitlement(self):
        with self.assertRaises(Problem):
            derive_sickness_entitlement(sickness(episode('2026-05-17','2026-07-10'),complete_from='2026-05-01'))
        with self.assertRaises(Problem):
            derive_sickness_entitlement(sickness(episode('2026-06-01','2026-07-15'),
                episode('2026-07-01','2026-08-01',identity='e',group='f')))
        source=sickness(episode('2026-05-17','2026-07-10'));source['remaining_days']=42
        with self.assertRaises(Problem):derive_sickness_entitlement(source)

    def test_evidenced_six_month_quiet_history_can_start_after_employment(self):
        row=derive_sickness_entitlement(sickness(episode('2026-07-01','2026-08-12'),
            complete_from='2026-01-01'))['episodes'][0]
        self.assertEqual(42,row['entitlement_calendar_days'])

    def test_calendar_month_end_is_neither_thirty_days_nor_clamped_anniversary(self):
        expected={'2026-01-01':'2026-01-31','2026-02-01':'2026-02-28',
            '2026-01-28':'2026-02-27','2026-01-29':'2026-02-28',
            '2026-01-30':'2026-02-28','2026-01-31':'2026-02-28',
            '2026-03-16':'2026-04-15','2024-01-31':'2024-02-29'}
        for start,end in expected.items():
            with self.subTest(start=start):self.assertEqual(end,calendar_month_period_end(start).isoformat())

    def test_unpaid_calendar_month_and_separate_tax_and_membership(self):
        plan=derive_unpaid_continuation(unpaid('2026-03-16','2026-05-02'))
        self.assertEqual('2026-04-15',plan['continuation_windows'][0]['statutory_deadline'])
        self.assertEqual([31,17],[r['calendar_days'] for r in plan['intervals']])
        self.assertTrue(plan['intervals'][0]['employment_for_contributions_continues'])
        self.assertFalse(plan['intervals'][1]['employment_for_contributions_continues'])
        self.assertFalse(plan['tax_lzz_reduced_by_unpaid_days'])
        self.assertFalse(plan['insurance_membership_determined'])

    def test_actual_benefit_exclusion_not_inferred_and_following_month_separate(self):
        source=unpaid('2026-02-01','2026-03-15')
        source['exceptions']=[dict(kind='sickness_benefit',**{'from':'2026-02-10','to':'2026-02-20'},employment_scope='this_employment',evidence_refs=[REF])]
        plan=derive_unpaid_continuation(source)
        self.assertEqual([9,11,23],[r['calendar_days'] for r in plan['intervals']])
        self.assertEqual(['2026-02-28','2026-03-20'],[r['statutory_deadline'] for r in plan['continuation_windows']])
        self.assertEqual('exception:sickness_benefit',plan['intervals'][1]['basis'])
        source['exceptions'][0]['kind']='assumed_sickness_benefit'
        with self.assertRaises(Problem):derive_unpaid_continuation(source)

    def test_published_aok_benefit_until_may_two_then_unpaid_until_june_thirteen(self):
        source=unpaid('2026-04-05','2026-06-13')
        source['exceptions']=[dict(kind='sickness_benefit',**{'from':'2026-04-05','to':'2026-05-02'},employment_scope='this_employment',evidence_refs=[REF])]
        plan=derive_unpaid_continuation(source)
        self.assertEqual([dict(**{'from':'2026-05-03'},statutory_deadline='2026-06-02',
            basis='after_evidenced_statutory_exclusion')],plan['continuation_windows'])
        self.assertEqual([28,31,11],[r['calendar_days'] for r in plan['intervals']])
        source['exceptions'][0]['employment_scope']='other_employment'
        with self.assertRaises(Problem):derive_unpaid_continuation(source)

    def test_inserted_paid_day_never_silently_renews_month(self):
        source=unpaid('2026-02-01','2026-04-01');source['intervening_paid_days']=['2026-03-01']
        with self.assertRaises(Problem):derive_unpaid_continuation(source)


class EntitlementMoneyTests(unittest.TestCase):
    def test_actual_2026_holidays_all_states_and_local_gaps_are_explicit(self):
        for state in STATES:
            self.assertEqual('christmas_day',public_holiday('2026-12-25',state))
            self.assertIsNone(public_holiday('2026-12-24',state))
            self.assertIsNone(public_holiday('2026-12-31',state))
        for state in ('HB','HH','NI','SH'):
            self.assertEqual('reformation',public_holiday('2026-10-31',state))
        self.assertIsNone(public_holiday('2026-10-31','BE'))
        self.assertEqual('international_womens_day',public_holiday('2026-03-08','MV'))
        self.assertEqual('easter_sunday',public_holiday('2026-04-05','BB'))
        self.assertIsNone(public_holiday('2026-04-05','BW'))
        self.assertEqual('world_childrens_day',public_holiday('2026-09-20','TH'))
        for current,state in (('2026-08-15','BY'),('2026-08-08','BY'),('2026-06-04','SN'),('2026-06-04','TH')):
            with self.assertRaises(Problem):public_holiday(current,state)

    def test_fixed_regular_hours_separate_actual_work_and_one_cent_rounding(self):
        source=dict(kind='first_sickness_day_regular_wage',hourly_rate_minor=1801,evidence_refs=[REF],
            days=[dict(date='2026-05-17',scheduled_regular_seconds=28800,worked_regular_seconds=14401,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[REF])])
        result=calculate_regular_absence_pay(source)
        self.assertEqual(14399,result['paid_absence_seconds'])
        self.assertEqual(7203,result['gross_minor']) # 1801 * 14399 / 3600 = 7203.4997...
        self.assertFalse(result['actual_project_time_modified'])
        self.assertEqual(14401,result['days'][0]['actual_work_seconds'])

    def test_holiday_unexcused_adjacent_day_excludes_pay(self):
        source=dict(kind='public_holiday',hourly_rate_minor=2000,evidence_refs=[REF],
            days=[dict(date='2026-01-01',scheduled_regular_seconds=28800,worked_regular_seconds=0,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=True,evidence_refs=[REF])])
        self.assertEqual(0,calculate_regular_absence_pay(source)['gross_minor'])
        source['days'][0]['holiday_adjacent_unexcused']=False
        self.assertEqual(16000,calculate_regular_absence_pay(source)['gross_minor'])

    def test_vacation_thirteen_weeks_five_days_without_actual_project_time(self):
        plan=calculate_vacation_reference(vacation())
        self.assertEqual(dict(numerator=650000,denominator=65),plan['workday_average'])
        self.assertEqual((50000,144000),(plan['gross_minor'],plan['paid_absence_seconds']))
        self.assertFalse(plan['actual_project_time_modified'])
        self.assertEqual('2026-10-05',plan['due_before'])

    def test_vacation_overtime_protected_loss_permanent_raise_and_in_kind(self):
        source=vacation();item=next(d for d in source['reference_days'] if d['contractual_workday'])
        item.update(base_earnings_minor=11000,overtime_earnings_minor=3000,protected_reduction_minor=2000,permanent_raise_minor=6500)
        source['in_kind_daily_minor']=400
        self.assertEqual(52500,calculate_vacation_reference(source)['gross_minor'])

    def test_no_daily_average_rounding_or_reference_holes(self):
        source=vacation();item=next(d for d in source['reference_days'] if d['contractual_workday'])
        item['base_earnings_minor']+=32 # 650032/65*5 = 50002.4615, daily rounding would lose 2 cents.
        self.assertEqual(50002,calculate_vacation_reference(source)['gross_minor'])
        bad=deepcopy(source);bad['reference_days'][0]['date']='2026-01-01'
        with self.assertRaises(Problem):calculate_vacation_reference(bad)
        bad=deepcopy(source);bad['reference_days'].pop()
        with self.assertRaises(Problem):calculate_vacation_reference(bad)

    def test_missing_evidence_or_forged_unknown_field_rejected(self):
        source=vacation();source['reference_days'][0]['evidence_refs']=[]
        with self.assertRaises(Problem):calculate_vacation_reference(source)
        source=vacation();source['gross_minor']=1
        with self.assertRaises(Problem):calculate_vacation_reference(source)

    def test_deterministic_plan_changes_with_actual_source_and_does_not_mutate_input(self):
        source=vacation();before=deepcopy(source)
        first=calculate_vacation_reference(source)
        self.assertEqual(first,calculate_vacation_reference(source));self.assertEqual(before,source)
        source['evidence_refs']=[dict(REF,revision=2)]
        second=calculate_vacation_reference(source)
        self.assertEqual(first['gross_minor'],second['gross_minor'])
        self.assertNotEqual(first['source_hash'],second['source_hash'])
        self.assertNotEqual(first['plan_hash'],second['plan_hash'])


if __name__=='__main__':unittest.main()
