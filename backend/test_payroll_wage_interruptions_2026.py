"""Independent calendar expectations for the first explicit U assessment."""
from copy import deepcopy
from datetime import date,timedelta
import unittest

from core import Problem
from payroll_wage_interruptions_2026 import calculate_wage_interruptions

REF=dict(id='1'*32,revision=1,content_hash='a'*64)


class WageInterruptionRules(unittest.TestCase):
    def source(self,start='2026-10-01',end='2026-10-31',lost=()):
        first,last=date.fromisoformat(start),date.fromisoformat(end)
        days=[]
        for index in range((last-first).days+1):
            current=first+timedelta(days=index)
            days.append(dict(date=current.isoformat(),contractual_workday=current.weekday()<5,
                wage_claim='none' if current.isoformat() in lost else 'preserved',section41_1_4_payment_kind='none',
                claim_evidence_refs=[REF],schedule_evidence_refs=[REF],exception_evidence_refs=[REF]))
        return dict(year=2026,assessment_through=end,employment_intervals=[dict(**{'from':start,'to':end},evidence_refs=[REF])],
            days=days,carry_in_loss=False,tax_scope='individual')

    def test_four_workdays_do_not_create_u_and_fifth_does(self):
        source=self.source(lost=['2026-10-'+str(n) for n in range(19,23)])
        self.assertEqual(0,calculate_wage_interruptions(source)['number_u'])
        source['days'][22]['wage_claim']='none'
        self.assertEqual(1,calculate_wage_interruptions(source)['number_u'])

    def test_five_calendar_days_with_weekend_are_only_three_workdays(self):
        result=calculate_wage_interruptions(self.source(lost=['2026-10-'+str(n) for n in range(23,28)]))
        self.assertEqual(0,result['number_u']);self.assertEqual(3,result['candidates'][0]['workday_count'])

    def test_weekend_and_month_boundary_do_not_duplicate_one_period(self):
        dates=['2026-10-29','2026-10-30','2026-11-02','2026-11-03','2026-11-04']
        result=calculate_wage_interruptions(self.source('2026-10-29','2026-11-04',dates))
        self.assertEqual(1,result['number_u']);self.assertEqual(dates,result['periods'][0]['qualifying_workdays'])

    def test_actual_paid_workday_splits_two_independent_periods(self):
        dates=['2026-10-'+str(n).zfill(2) for n in (*range(5,10),*range(13,20))]
        result=calculate_wage_interruptions(self.source(lost=dates))
        self.assertEqual(2,result['number_u']);self.assertEqual([5,5],[v['workday_count'] for v in result['periods']])

    def test_individual_contractual_parttime_schedule_counts_actual_workdays(self):
        source=self.source(lost=['2026-10-'+str(n).zfill(2) for n in range(1,32)])
        for row in source['days']:row['contractual_workday']=date.fromisoformat(row['date']).weekday()==0
        result=calculate_wage_interruptions(source)
        self.assertEqual(4,result['candidates'][0]['workday_count']);self.assertEqual(0,result['number_u'])

    def test_actual_departure_and_reentry_do_not_share_five_day_threshold(self):
        source=self.source(lost=['2026-10-'+str(n).zfill(2) for n in range(1,32)])
        source['employment_intervals']=[dict(**{'from':'2026-10-05','to':'2026-10-07'},evidence_refs=[REF]),
            dict(**{'from':'2026-10-12','to':'2026-10-14'},evidence_refs=[REF])]
        source['days']=[v for v in source['days'] if any(p['from']<=v['date']<=p['to'] for p in source['employment_intervals'])]
        result=calculate_wage_interruptions(source)
        self.assertEqual([3,3],[v['workday_count'] for v in result['candidates']]);self.assertEqual(0,result['number_u'])

    def test_section41_sentence4_payment_excludes_qualifying_period(self):
        source=self.source(lost=['2026-10-'+str(n) for n in range(19,24)])
        for row in source['days'][18:23]:row['section41_1_4_payment_kind']='qualification_benefit'
        self.assertEqual(0,calculate_wage_interruptions(source)['number_u'])

    def test_unknown_exception_partial_claim_carryin_and_minijob_do_not_invent_zero(self):
        source=self.source(lost=['2026-10-'+str(n) for n in range(19,24)])
        variants=[]
        changed=deepcopy(source);changed['days'][20]['section41_1_4_payment_kind']=None;variants.append(changed)
        changed=deepcopy(source);changed['days'][20]['wage_claim']='partial_unknown';variants.append(changed)
        variants.extend([source|dict(carry_in_loss=True),source|dict(tax_scope='flat_minijob')])
        for changed in variants:
            result=calculate_wage_interruptions(changed)
            self.assertFalse(result['can_determine']);self.assertIsNone(result['number_u'])

    def test_missing_calendar_day_foreign_day_and_unknown_version_are_rejected(self):
        source=self.source()
        for changed in (source|dict(days=source['days'][:-1]),source|dict(days=source['days']+[source['days'][0]])):
            with self.assertRaises(Problem):calculate_wage_interruptions(changed)
        with self.assertRaises(Problem):calculate_wage_interruptions(source,'future_version')


if __name__=='__main__':unittest.main()
