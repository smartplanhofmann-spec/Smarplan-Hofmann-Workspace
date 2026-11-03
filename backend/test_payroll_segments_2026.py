"""Independent contractual arithmetic and true/cosmetic SV split boundaries."""
from copy import deepcopy
from datetime import date,timedelta
import unittest

from core import Problem
from payroll_segments_2026 import contractual_earnings,employment_intervals,reference,social_intervals


def sources(month='2026-07',method='calendar_days_actual'):
    def record(key,kind,**values):return dict(id=key*32,revision=1,content_hash=key*64,employee_id='e'*32,kind=kind,**values)
    left=record('a','agreement',effective_from='2026-01-01',employment_kind='regular',pay_basis='monthly',amount_minor=300000)
    right=record('b','agreement',effective_from=month+'-16',employment_kind='regular',pay_basis='monthly',amount_minor=400000)
    terms=record('c','employment_terms',status='active',details=dict(employment_from='2026-01-01',employment_to=None,
        agreement_refs=[reference(left),reference(right)],proration_method=method))
    return terms,[left,right]


class SegmentedEarningsTests(unittest.TestCase):
    def test_two_monthly_agreements_use_actual_contractual_days_without_new_social_caps(self):
        terms,agreements=sources();before=deepcopy((terms,agreements))
        result=contractual_earnings('2026-07',[terms],agreements,[])
        self.assertEqual(result['blockers'],[])
        self.assertEqual([value['gross_minor'] for value in result['earnings']],[145161,206452])
        self.assertEqual(result['gross_minor'],351613)
        social=social_intervals('2026-07',result['employment_intervals'],[])
        self.assertEqual(len(social),1);self.assertEqual(social[0]['days'],30)
        self.assertEqual(social[0]['caps']['health_minor'],581250)
        self.assertEqual((terms,agreements),before)

    def test_hourly_changes_use_actual_approved_days_and_round_each_real_claim_once(self):
        terms,agreements=sources()
        agreements[0].update(pay_basis='hourly',amount_minor=1234);agreements[1].update(pay_basis='hourly',amount_minor=2000)
        result=contractual_earnings('2026-07',[terms],agreements,[dict(date='2026-07-15',net_seconds=4500),dict(date='2026-07-16',net_seconds=900)])
        self.assertEqual([value['gross_minor'] for value in result['earnings']],[1543,500])
        self.assertEqual(result['approved_work_seconds'],5400)
        self.assertEqual(result['gross_minor'],2043)

    def test_schedule_methods_keep_whole_month_denominator(self):
        terms,agreements=sources(method='scheduled_workdays')
        days=[]
        for index in range(31):
            current=date(2026,7,1)+timedelta(days=index)
            days.append(dict(date=current.isoformat(),scheduled_seconds=(21600 if current.day<=15 else 28800) if current.weekday()<5 else 0))
        schedule=dict(id='d'*32,revision=1,content_hash='d'*64,employee_id='e'*32,kind='work_schedule',status='active',details=dict(month='2026-07',days=days))
        result=contractual_earnings('2026-07',[terms],agreements,[],schedule=schedule)
        self.assertEqual([(value['numerator'],value['denominator']) for value in result['earnings']],[(11,23),(12,23)])
        self.assertEqual(result['gross_minor'],352174)
        terms['details']['proration_method']='scheduled_seconds'
        result=contractual_earnings('2026-07',[terms],agreements,[],schedule=schedule)
        self.assertEqual(result['gross_minor'],359259)

    def test_thirty_day_segment_choice_is_explicit_and_not_inferred_from_social_days(self):
        terms,agreements=sources(method='contractual_30_days')
        result=contractual_earnings('2026-07',[terms],agreements,[])
        self.assertIsNone(result['gross_minor']);self.assertEqual(result['blockers'][0]['code'],'segment_contract_method_missing')
        result=contractual_earnings('2026-07',[terms],agreements,[],thirty_day_rule='actual_days_capped_per_claim')
        self.assertEqual([value['gross_minor'] for value in result['earnings']],[150000,213333])
        self.assertEqual(social_intervals('2026-07',result['employment_intervals'],[])[0]['days'],30)

    def test_full_february_single_contract_still_has_full_month_entitlement(self):
        terms,agreements=sources(month='2026-02',method='contractual_30_days')
        result=contractual_earnings('2026-02',[terms],agreements[:1],[],thirty_day_rule='actual_days_capped_per_claim')
        self.assertEqual(result['gross_minor'],300000)
        self.assertEqual(result['earnings'][0]['numerator'],30)
        self.assertEqual(result['employment_intervals'][0]['calendar_days'],28)

    def test_unpaid_day_is_removed_before_rounding_and_keeps_contract_basis_separate(self):
        terms,agreements=sources(month='2026-02',method='contractual_30_days')
        result=contractual_earnings('2026-02',[terms],agreements[:1],[],thirty_day_rule='actual_days_capped_per_claim',unpaid_dates=['2026-02-12'])
        self.assertEqual(result['gross_minor'],290000)
        terms['details']['proration_method']='calendar_days_actual'
        result=contractual_earnings('2026-02',[terms],agreements[:1],[],unpaid_dates=['2026-02-12'])
        self.assertEqual(result['gross_minor'],289286)
        self.assertEqual(social_intervals('2026-02',result['employment_intervals'],[])[0]['days'],30)

    def test_explicitly_unpaid_day_cannot_also_contain_work(self):
        terms,agreements=sources()
        result=contractual_earnings('2026-07',[terms],agreements,[dict(date='2026-07-15',net_seconds=3600)],unpaid_dates=['2026-07-15'])
        self.assertIn('work_on_fully_unpaid_day',[value['code'] for value in result['blockers']])

    def test_missing_contract_binding_and_work_outside_employment_are_visible(self):
        terms,agreements=sources();terms['details'].update(employment_from='2026-07-10',agreement_refs=[reference(agreements[0])])
        result=contractual_earnings('2026-07',[terms],agreements,[dict(date='2026-07-09',net_seconds=3600)])
        self.assertEqual({value['code'] for value in result['blockers']},{'agreement_source_mismatch','work_outside_employment'})

    def test_duplicate_effective_date_or_day_does_not_double_count(self):
        terms,agreements=sources();other=deepcopy(agreements[1]);other['effective_from']=agreements[0]['effective_from']
        with self.assertRaises(Problem):contractual_earnings('2026-07',[terms],[agreements[0],other],[])
        with self.assertRaises(Problem):contractual_earnings('2026-07',[terms],agreements,[dict(date='2026-07-15',net_seconds=1)]*2)

    def test_existing_v4_blocked_plan_is_not_mutated_by_new_earnings_builder(self):
        from test_payroll_periods_2026 import period_snapshot
        from payroll_periods_2026 import build_period_plan
        source=period_snapshot(month='2026-07',start='2026-07-01',end='2026-07-31',method='calendar_days_actual')
        terms,agreements=sources();source['employment_terms']=terms
        source['preparation']['snapshot']['agreements']=agreements
        source['preparation']['snapshot']['employee'].update(employment_from=terms['details']['employment_from'],employment_to=None)
        old=build_period_plan(source);self.assertFalse(old['can_calculate'])
        contractual_earnings('2026-07',[terms],agreements,[])
        self.assertEqual(build_period_plan(source),old)
        self.assertIn('multiple_wage_agreements',[value['code'] for value in old['blockers']])


class SocialSegmentIntervalsTests(unittest.TestCase):
    def event(self,date,reason='contribution_group_change'):
        return dict(effective_from=date,reason=reason,source_ref=dict(id='f'*32,revision=1,content_hash='f'*64))

    def test_published_july_group_change_has_15_plus_16_days(self):
        terms,_=sources();episodes=employment_intervals('2026-07',[terms])
        result=social_intervals('2026-07',episodes,[self.event('2026-07-16')])
        self.assertEqual([value['days'] for value in result],[15,16])
        self.assertEqual([value['caps']['health_minor'] for value in result],[290625,310000])
        self.assertEqual([value['caps']['pension_minor'] for value in result],[422500,450667])

    def test_february_true_split_does_not_apply_reporting_tolerance_to_payroll(self):
        terms,_=sources('2026-02');episodes=employment_intervals('2026-02',[terms])
        result=social_intervals('2026-02',episodes,[self.event('2026-02-15')])
        self.assertEqual([value['days'] for value in result],[14,14])
        self.assertEqual([value['caps']['health_minor'] for value in result],[271250,271250])
        self.assertEqual([value['caps']['pension_minor'] for value in result],[394333,394333])

    def test_thirty_day_month_true_split_matches_month_days_but_has_own_rounding(self):
        terms,_=sources('2026-04');episodes=employment_intervals('2026-04',[terms])
        result=social_intervals('2026-04',episodes,[self.event('2026-04-16')])
        self.assertEqual([value['days'] for value in result],[15,15])
        self.assertEqual(sum(value['caps']['pension_minor'] for value in result),845000)

    def test_tax_and_cosmetic_profile_changes_cannot_create_new_cap(self):
        terms,_=sources();episodes=employment_intervals('2026-07',[terms])
        for reason in ('tax_features_change','wage_agreement_change','health_fund_name_change','arbitrary_split'):
            with self.subTest(reason=reason),self.assertRaises(Problem):social_intervals('2026-07',episodes,[self.event('2026-07-16',reason)])

    def test_actual_exit_and_resumption_keep_gap_outside_both_intervals(self):
        first,_=sources();second=deepcopy(first);second.update(id='d'*32,content_hash='d'*64)
        first['details'].update(employment_from='2026-07-05',employment_to='2026-07-10')
        second['details'].update(employment_from='2026-07-20',employment_to='2026-07-31')
        episodes=employment_intervals('2026-07',[second,first])
        result=social_intervals('2026-07',episodes,[])
        self.assertEqual([value['days'] for value in result],[6,12])
        self.assertEqual([value['caps']['health_minor'] for value in result],[116250,232500])
        with self.assertRaises(Problem):social_intervals('2026-07',episodes,[self.event('2026-07-15')])
        second['details']['employment_from']='2026-07-10'
        with self.assertRaises(Problem):employment_intervals('2026-07',[first,second])


if __name__=='__main__':unittest.main()
