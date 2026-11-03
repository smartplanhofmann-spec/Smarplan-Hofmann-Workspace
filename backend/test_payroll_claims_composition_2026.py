"""Independent no-double-pay and actual time boundaries for P3b/P4 composition."""
from copy import deepcopy
from datetime import date,timedelta
import calendar
import unittest

from core import Problem
from payroll_claims_composition_2026 import compose_claims
from payroll_entitlements_2026 import build_entitlement_plan
from payroll_segments_2026 import reference
from test_payroll_segments_2026 import sources
from test_payroll_entitlements_2026 import REF,episode,sickness,unpaid


def fixture(month='2026-07',basis='monthly',amount=300000):
    terms,agreements=sources(month);agreements=agreements[:1];agreements[0].update(pay_basis=basis,amount_minor=amount)
    terms['details']['agreement_refs']=[reference(agreements[0])]
    preparation=dict(id='1'*32,revision=1,content_hash='1'*64,employee_id='e'*32,kind='preparation',month=month,
        snapshot=dict(approved_days=[],approved_absences=[],net_work_seconds=0))
    year,number=map(int,month.split('-'))
    schedule=dict(id='2'*32,revision=1,content_hash='2'*64,employee_id='e'*32,kind='work_schedule',status='active',
        details=dict(month=month,days=[dict(date=date(year,number,index).isoformat(),scheduled_seconds=28800)
            for index in range(1,calendar.monthrange(year,number)[1]+1)]))
    return terms,agreements,preparation,schedule


def fact(kind,input,terms,identity='3'):
    details=dict(employment_terms_ref=reference(terms),input=input)
    snapshot=dict(schema_version=1,kind=kind,details=details)
    return dict(id=identity*32,revision=1,content_hash=identity*64,employee_id='e'*32,status='active',kind=kind,
        details=details,sources=snapshot,plan=build_entitlement_plan(snapshot))


class ClaimsCompositionTests(unittest.TestCase):
    def test_current_sickness_onset_requires_actual_work_and_schedule(self):
        for onset,actual,scheduled in (('during_work',0,28800),('before_work',14400,28800),('non_workday',0,28800)):
            with self.subTest(onset=onset):
                terms,agreements,prep,schedule=fixture()
                prep['snapshot']['approved_days']=[dict(date='2026-07-06',net_seconds=actual)]
                schedule['details']['days'][5]['scheduled_seconds']=scheduled
                history=fact('sickness_history',sickness(episode('2026-07-06','2026-07-10',onset=onset),start='2026-01-01'),terms)
                result=compose_claims('2026-07',[terms],agreements,prep,[history],schedule=schedule)
                self.assertIn('sickness_onset_work_mismatch',[value['code'] for value in result['blockers']])

    def test_monthly_vacation_keeps_single_salary(self):
        terms,agreements,prep,schedule=fixture();prep['snapshot']['approved_absences']=[dict(kind='vacation',start_date='2026-07-06',end_date='2026-07-10')]
        result=compose_claims('2026-07',[terms],agreements,prep,[],schedule=schedule)
        self.assertEqual(result['gross_minor'],300000);self.assertEqual(result['absence_earnings'],[]);self.assertEqual(result['blockers'],[])

    def test_monthly_paid_sickness_proves_entitlement_without_adding_salary(self):
        terms,agreements,prep,schedule=fixture();prep['snapshot']['approved_absences']=[dict(kind='sick',start_date='2026-07-06',end_date='2026-07-10')]
        history=fact('sickness_history',sickness(episode('2026-07-06','2026-07-10'),start='2026-01-01'),terms)
        result=compose_claims('2026-07',[terms],agreements,prep,[history],schedule=schedule)
        self.assertEqual(result['gross_minor'],300000);self.assertEqual(result['absence_earnings'],[]);self.assertEqual(result['blockers'],[])

    def test_monthly_unpaid_days_reduce_exact_contract_once_and_keep_sv_facts_separate(self):
        terms,agreements,prep,schedule=fixture()
        continuation=fact('unpaid_continuation',unpaid('2026-07-10','2026-07-20'),terms)
        result=compose_claims('2026-07',[terms],agreements,prep,[continuation],schedule=schedule)
        self.assertEqual(result['gross_minor'],193548)
        self.assertEqual(len(result['unpaid_dates']),11)
        self.assertTrue(all(value['employment_for_contributions_continues'] for value in result['social_continuation']))
        self.assertEqual(result['blockers'],[])

    def test_exhausted_sickness_needs_actual_social_history_and_does_not_assume_benefit(self):
        terms,agreements,prep,schedule=fixture();prep['snapshot']['approved_absences']=[dict(kind='sick',start_date='2026-07-01',end_date='2026-07-31')]
        history=fact('sickness_history',sickness(episode('2026-06-01','2026-07-31'),start='2026-01-01'),terms)
        result=compose_claims('2026-07',[terms],agreements,prep,[history],schedule=schedule)
        self.assertIn('unpaid_social_evidence_missing',[value['code'] for value in result['blockers']])
        continuation=fact('unpaid_continuation',unpaid('2026-07-13','2026-07-31'),terms,'4')
        result=compose_claims('2026-07',[terms],agreements,prep,[history,continuation],schedule=schedule)
        self.assertEqual(result['gross_minor'],116129);self.assertEqual(result['blockers'],[])

    def test_first_sickness_day_only_pays_missing_seconds_and_preserves_actual_time(self):
        terms,agreements,prep,schedule=fixture('2026-05','hourly',1801)
        prep['snapshot'].update(approved_days=[dict(date='2026-05-17',net_seconds=14401)],net_work_seconds=14401,
            approved_absences=[dict(kind='sick',start_date='2026-05-17',end_date='2026-05-17')])
        before=deepcopy(prep)
        history=fact('sickness_history',sickness(episode('2026-05-17','2026-05-17',onset='during_work'),start='2026-01-01',pay_basis='hourly'),terms)
        regular=dict(kind='first_sickness_day_regular_wage',hourly_rate_minor=1801,evidence_refs=[REF],
            days=[dict(date='2026-05-17',scheduled_regular_seconds=28800,worked_regular_seconds=14401,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[REF])])
        paid=fact('regular_absence',regular,terms,'4')
        result=compose_claims('2026-05',[terms],agreements,prep,[history,paid],schedule=schedule)
        self.assertEqual(result['gross_minor'],14408);self.assertEqual(result['absence_earnings'][0]['gross_minor'],7203)
        self.assertEqual(result['absence_earnings'][0]['paid_absence_seconds'],14399)
        self.assertEqual(result['blockers'],[]);self.assertEqual(prep,before)

    def test_duplicate_absence_case_and_monthly_hourly_mismatch_block(self):
        terms,agreements,prep,schedule=fixture('2026-01','hourly',2000)
        regular=dict(kind='public_holiday',hourly_rate_minor=2000,evidence_refs=[REF],days=[dict(date='2026-01-01',
            scheduled_regular_seconds=28800,worked_regular_seconds=0,entitled=True,absence_is_only_cause=True,
            holiday_adjacent_unexcused=False,evidence_refs=[REF])])
        left=fact('regular_absence',regular,terms);right=fact('regular_absence',regular,terms,'4')
        result=compose_claims('2026-01',[terms],agreements,prep,[left,right],schedule=schedule)
        self.assertIn('duplicate_absence_pay',[value['code'] for value in result['blockers']])
        agreements[0].update(pay_basis='monthly',amount_minor=300000)
        result=compose_claims('2026-01',[terms],agreements,prep,[left],schedule=schedule)
        self.assertIn('absence_wage_mismatch',[value['code'] for value in result['blockers']])
        self.assertEqual(result['gross_minor'],300000)

    def test_vacation_cross_month_uses_exact_reference_only_for_actual_month_days(self):
        first=date(2026,9,28);history=[]
        for index in range(91):
            current=first-timedelta(days=91-index);workday=current.weekday()<5
            history.append(dict(date=current.isoformat(),contractual_workday=workday,base_earnings_minor=10000 if workday else 0,
                overtime_earnings_minor=0,protected_reduction_minor=0,permanent_raise_minor=0,evidence_refs=[REF]))
        value=dict(vacation_from='2026-09-28',vacation_to='2026-10-02',reference_days=history,
            vacation_days=[dict(date=(first+timedelta(days=index)).isoformat(),scheduled_regular_seconds=28800,evidence_refs=[REF]) for index in range(5)],
            in_kind_daily_minor=0,evidence_refs=[REF])
        for month,expected in (('2026-09',30000),('2026-10',20000)):
            terms,agreements,prep,schedule=fixture(month,'hourly',1250)
            prep['snapshot']['approved_absences']=[dict(kind='vacation',start_date='2026-09-28',end_date='2026-10-02')]
            vacation=fact('vacation_reference',value,terms)
            result=compose_claims(month,[terms],agreements,prep,[vacation],schedule=schedule)
            self.assertEqual(result['gross_minor'],expected);self.assertEqual(result['blockers'],[])

    def test_paid_sickness_and_unpaid_facts_cannot_both_apply(self):
        terms,agreements,prep,schedule=fixture()
        history=fact('sickness_history',sickness(episode('2026-07-06','2026-07-10'),start='2026-01-01'),terms)
        continuation=fact('unpaid_continuation',unpaid('2026-07-06','2026-07-10'),terms,'4')
        result=compose_claims('2026-07',[terms],agreements,prep,[history,continuation],schedule=schedule)
        self.assertIn('paid_and_unpaid_overlap',[value['code'] for value in result['blockers']])

    def test_changed_claim_plan_fails_arithmetic_replay(self):
        terms,agreements,prep,schedule=fixture()
        continuation=fact('unpaid_continuation',unpaid('2026-07-10','2026-07-20'),terms)
        continuation['plan']['intervals'][0]['employment_for_contributions_continues']=False
        with self.assertRaises(Problem):compose_claims('2026-07',[terms],agreements,prep,[continuation],schedule=schedule)


if __name__=='__main__':unittest.main()
