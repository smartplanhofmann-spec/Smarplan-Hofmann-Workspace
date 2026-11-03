"""Independent official values and evidenced partial-month boundary cases."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from core import Problem
from payroll_de_2026 import normalize_profile
from payroll_pap_periods_2026 import calculate_daily_tax, calculate_period_tax, daily_tax_feature
from payroll_periods_2026 import build_period_plan, calculate_period_source, partial_caps


def period_snapshot(*,month='2026-03',start='2026-03-01',end='2026-03-16',amount=500000,
                    kind='regular',method='contractual_30_days',**changes):
    profile=normalize_profile(dict(effective_from='2026-01-01',employment_kind=kind,date_of_birth='1990-01-01',
        federal_state='BW',tax_class=1,tax_children_half_units=0,church_tax='none',
        health_insurance='statutory_mandatory',health_fund='Synthetic Fund',health_additional_percent='2.90',
        has_children=False,pv_children_under_25=0,u1_required=True,u1_percent='0.800' if kind=='minijob' else '2.000',
        u2_percent='0.220' if kind=='minijob' else '0.300',minijob_rv_exempt=False,minijob_tax='flat_2_employer' if kind=='minijob' else 'individual',
        pension_other_compulsory=False,regular_annual_gross_minor=amount*12,special_cases=[],verification_note='Synthetic independently evidenced profile',
        **({} if kind=='minijob' else dict(tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0))))
    profile.update(changes);profile=normalize_profile(profile)
    def record(key,kind,**values):return dict(id=key*32,revision=1,content_hash=key*64,employee_id='e'*32,kind=kind,**values)
    ref=lambda value:{key:value[key] for key in ('id','revision','content_hash')}
    agreement=record('a','agreement',effective_from='2026-01-01',employment_kind=kind,pay_basis='monthly',amount_minor=amount)
    employee=dict(id='e'*32,user_id=None,name='Synthetic Employee',employment_from=start,employment_to=end,revision=1)
    preparation=record('b','preparation',month=month,snapshot=dict(schema_version=1,month=month,employee=employee,
        agreements=[agreement],approved_days=[],corrections=[],approved_absences=[],expenses=[],net_work_seconds=0))
    profile_record=record('c','profile',profile=profile)
    identity=record('d','identity',details=dict(profile_id=profile_record['id'],profile_revision=1,
        valid_from=start,valid_to=end or '2026-12-31',employment_from=start,employment_to=end))
    terms=record('f','employment_terms',status='active',details=dict(employment_from=start,employment_to=end,
        agreement_refs=[ref(agreement)],proration_method=method,reason='Explicit original contract quotient'))
    case=dict(month=month,preparation_ref=ref(preparation),employment_terms_ref=ref(terms),work_schedule_ref=None,
        profile_refs=[ref(profile_record)],identity_refs=[ref(identity)],tax_treatment='domestic_running_wages',
        entitlement_decisions=[],verification_note='Explicit synthetic actual period')
    return dict(schema_version=1,employee_id=employee['id'],month=month,preparation=preparation,
        profiles=[profile_record],identities=[identity],employment_terms=terms,work_schedule=None,case_details=case,source_files=[])


class DailyPapPeriodsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.references=json.loads((Path(__file__).resolve().parent.parent/'docs/CRM_ERP_LOHN_TEILMONATE_REFERENZEN_2026-11-03.json').read_text())

    def args(self,case):
        return dict(tax_class=case['tax_class'],children_half_units=0,additional_health_percent='2.90',saxony=False,
            childless_surcharge=case['childless_surcharge'],care_child_discounts=0,church_member=case.get('church_member',False))

    def test_all_eighteen_official_annual_derived_daily_values(self):
        for case in self.references['daily_cases']:
            with self.subTest(case=case['id']):
                self.assertEqual(calculate_daily_tax(gross_minor=case['gross_minor'],allowance_minor=0,addition_minor=0,
                    **self.args(case)),case['expected'])

    def test_four_independently_derived_actual_periods(self):
        by_id={value['id']:value for value in self.references['daily_cases']}
        for case in self.references['multiple_day_cases']:
            reference=by_id[case['daily_reference']]|{key:value for key,value in case.items() if key=='church_member'}
            with self.subTest(case=case['id']):
                result=calculate_period_tax(gross_minor=case['gross_minor'],lzz=4,tax_days=case['tax_days'],
                    allowance_monthly_minor=0,addition_monthly_minor=0,**self.args(reference))
                self.assertEqual(result['totals'],case['expected'])

    def test_actual_gross_keeps_nondivisible_remainder(self):
        result=calculate_period_tax(gross_minor=37502,lzz=4,tax_days=3,allowance_monthly_minor=0,
            addition_monthly_minor=0,**self.args(self.references['daily_cases'][0]))
        self.assertEqual(result['inputs']['gross_minor'],37502)
        self.assertEqual(result['inputs']['pap_gross_minor'],12500)
        self.assertEqual(result['inputs']['gross_remainder_minor'],2)
        self.assertEqual(result['totals']['LSTLZZ'],4641)

    def test_explicit_monthly_feature_to_five_cent_daily_rounding(self):
        self.assertEqual(daily_tax_feature(10000),335)
        self.assertEqual(daily_tax_feature(15000),500)
        self.assertEqual(daily_tax_feature(1),5)
        self.assertEqual(daily_tax_feature(0),0)
        for value in (True,-1,'100'):
            with self.subTest(value=value),self.assertRaises(Problem):daily_tax_feature(value)


class PayrollPeriodPlanTests(unittest.TestCase):
    def test_drv_published_partial_caps_round_only_after_multiplication(self):
        self.assertEqual(partial_caps(12),dict(health_minor=232500,care_minor=232500,pension_minor=338000,unemployment_minor=338000))
        self.assertEqual(partial_caps(16),dict(health_minor=310000,care_minor=310000,pension_minor=450667,unemployment_minor=450667))

    def test_contractual_and_actual_calendar_wages_are_separate_from_social_days(self):
        source=period_snapshot();plan=build_period_plan(source)
        self.assertTrue(plan['can_calculate']);self.assertEqual(plan['gross_minor'],266667)
        self.assertEqual(plan['social_periods'][0]['days'],16)
        self.assertEqual(plan['tax_periods'][0]['tax_days'],16)
        actual=deepcopy(source);actual['employment_terms']['details']['proration_method']='calendar_days_actual'
        alternate=build_period_plan(actual)
        self.assertEqual(alternate['gross_minor'],258065)
        self.assertEqual(alternate['social_periods'][0]['caps'],plan['social_periods'][0]['caps'])
        self.assertNotEqual(alternate['plan_hash'],plan['plan_hash'])

    def test_february_full_month_and_actual_one_day_on_31st(self):
        full=build_period_plan(period_snapshot(month='2026-02',start='2026-02-01',end='2026-02-28'))
        self.assertEqual(full['gross_minor'],500000)
        self.assertEqual(full['employment_intervals'][0]['calendar_days'],28)
        self.assertEqual(full['social_periods'][0]['days'],30)
        self.assertEqual(full['tax_periods'][0]['lzz'],2)
        single=calculate_period_source(period_snapshot(month='2026-07',start='2026-07-31',end='2026-07-31',amount=375000))
        self.assertTrue(single['payroll_calculation_complete'])
        self.assertEqual(single['gross_minor'],12500)
        self.assertEqual(single['individual_wage_tax_minor'],1547)
        self.assertEqual(single['period_details']['social_periods'][0]['days'],1)

    def test_scheduled_workdays_and_seconds_use_whole_evidenced_month(self):
        from datetime import date,timedelta
        source=period_snapshot(method='scheduled_workdays')
        days=[]
        for i in range(31):
            current=date(2026,3,1)+timedelta(days=i)
            days.append(dict(date=current.isoformat(),scheduled_seconds=28800 if current.weekday()<5 else 0,workplace='Synthetic office',federal_state='BW'))
        schedule=dict(id='9'*32,revision=1,content_hash='9'*64,employee_id='e'*32,kind='work_schedule',status='active',details=dict(month='2026-03',days=days,reason='Original rota'))
        source['work_schedule']=schedule
        source['case_details']['work_schedule_ref']={key:schedule[key] for key in ('id','revision','content_hash')}
        plan=build_period_plan(source)
        self.assertEqual((plan['earnings'][0]['numerator'],plan['earnings'][0]['denominator']),(11,22))
        self.assertEqual(plan['gross_minor'],250000)
        source['employment_terms']['details']['proration_method']='scheduled_seconds'
        self.assertEqual(build_period_plan(source)['gross_minor'],250000)
        source['work_schedule']['details']['days'].pop()
        with self.assertRaises(Problem):build_period_plan(source)

    def test_minijob_proportional_minimum_and_regular_annual_forecast(self):
        source=period_snapshot(month='2026-04',start='2026-04-11',end='2026-04-30',amount=15000,kind='minijob')
        result=calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete']);self.assertEqual(result['gross_minor'],10000)
        self.assertEqual(result['period_details']['social_periods'][0]['minimum_pension_basis_minor'],11667)
        self.assertEqual(result['employee_contributions']['pension'],670)
        self.assertEqual(result['employer_contributions']['pension'],1500)
        self.assertEqual(result['net_minor'],9330)
        source['profiles'][0]['profile']['minijob_rv_exempt']=True
        self.assertEqual(calculate_period_source(source)['net_minor'],10000)

    def test_low_actual_partial_regular_wage_is_not_automatically_transition(self):
        result=calculate_period_source(period_snapshot(start='2026-03-25',end='2026-03-31',amount=300000))
        self.assertTrue(result['payroll_calculation_complete'])
        self.assertEqual(result['gross_minor'],70000)
        self.assertEqual(result['scope'],'regular_standard_period')
        self.assertEqual(result['employee_contributions']['pension'],6510)

    def test_prior_contract_references_do_not_replace_current_month_evidence(self):
        source=period_snapshot();current=source['employment_terms']['details']['agreement_refs'][0]
        source['employment_terms']['details']['agreement_refs'].insert(0,dict(id='8'*32,revision=1,content_hash='8'*64))
        self.assertTrue(build_period_plan(source)['can_calculate'])
        source['employment_terms']['details']['agreement_refs'].remove(current)
        self.assertIn('agreement_source_mismatch',[item['code'] for item in build_period_plan(source)['blockers']])

    def test_high_hourly_partial_wage_has_separate_caps_and_saxony_care_split(self):
        source=period_snapshot(federal_state='SN',has_children=True,pv_children_under_25=3)
        snapshot=source['preparation']['snapshot'];snapshot['agreements'][0].update(pay_basis='hourly',amount_minor=1000000)
        snapshot['net_work_seconds']=3600;snapshot['approved_days']=[dict(date='2026-03-01',net_seconds=3600)]
        result=calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete']);self.assertEqual(result['gross_minor'],1000000)
        self.assertEqual(result['employee_contributions'],dict(health_general=22630,health_additional=4495,pension=41912,unemployment=5859,care=5580))
        self.assertEqual(result['employer_contributions'],dict(health_general=22630,health_additional=4495,pension=41912,unemployment=5859,care=4030))
        self.assertEqual(result['employer_levies'],dict(u1=9013,u2=1352,insolvency=676))

    def test_transition_uses_contractual_ratio_and_preserves_forecast(self):
        assessment=dict(status='within_transition_area',assessed_on='2026-01-01',regular_monthly_gross_minor=100000,
            forecast_months=12,foreseeable_one_off_payments=False,note='Independent actual forecast')
        source=period_snapshot(month='2026-04',start='2026-04-16',end='2026-04-30',amount=100000,transition_assessment=assessment)
        result=calculate_period_source(source)
        self.assertTrue(result['payroll_calculation_complete']);self.assertEqual(result['gross_minor'],50000)
        bases=result['period_details']['transition']
        self.assertEqual(bases['total_assessment_minor'],42703)
        self.assertEqual(bases['employee_assessment_minor'],28418)
        self.assertEqual(bases['regular_monthly_gross_minor'],100000)
        self.assertEqual(bases['monthly_equivalent_minor'],'100000')

    def test_absence_does_not_silently_shorten_any_statutory_period(self):
        source=period_snapshot(start='2026-03-01',end='2026-03-31')
        source['preparation']['snapshot']['approved_absences']=[dict(kind='sick',start_date='2026-03-10',end_date='2026-03-12')]
        plan=build_period_plan(source);result=calculate_period_source(source)
        self.assertEqual(plan['tax_periods'][0]['lzz'],2)
        self.assertEqual(plan['social_periods'][0]['days'],30)
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertIsNone(result['net_minor'])
        self.assertIn('entitlement_requires_calculation',[value['code'] for value in result['blockers']])

    def test_missing_identity_mismatched_stammdaten_and_changed_profile_block(self):
        for mutation,code in ((lambda s:s['identities'].clear(),'period_identity_missing'),
                (lambda s:s['employment_terms']['details'].update(employment_from='2026-03-02'),'employment_source_mismatch'),
                (lambda s:s['profiles'][0]['profile'].update(effective_from='2026-03-03'),'profile_changed_in_period')):
            source=period_snapshot();mutation(source)
            with self.subTest(code=code):
                result=calculate_period_source(source)
                self.assertFalse(result['payroll_calculation_complete'])
                self.assertIn(code,[value['code'] for value in result['blockers']])


if __name__=='__main__':unittest.main()
