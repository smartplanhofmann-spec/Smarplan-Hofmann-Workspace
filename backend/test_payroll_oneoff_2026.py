"""Independent published SV example and explicitly derived 2025/26 boundaries."""
import calendar
import copy
import json
from pathlib import Path
import unittest

from core import Problem
from payroll_oneoff_2026 import (annual_social_room,select_one_off_assignment,transition_bases,classify_regular_pay,
    assess_social_contributions,calculate_regular_one_off_contributions,reassess_transition_one_off,
    assess_minijob_unforeseen_month,calculate_minijob_one_off_contributions)


def ref(number):return dict(id=f'{number:032x}',revision=1,content_hash=f'{number:064x}')


def basis(year,through,pay,first_month=1):
    periods=[]
    for month in range(first_month,int(through[5:7])+1):
        start=f'{year}-{month:02}-01';end=f'{year}-{month:02}-{calendar.monthrange(year,month)[1]}'
        original=ref(year*100+month)
        branches={key:dict(eligible_intervals=[dict(start=start,end=end,legal_reason='paid_employment',source_ref=original)],
                           contributed_minor=pay) for key in ('health','care','pension','unemployment')}
        periods.append(dict(source_ref=original,part_key='regular',section_key='regular',start=start,end=end,branches=branches))
    return dict(year=year,employee_id='a'*32,employer_key='test-legal-employer',coverage_to=through,
                periods=periods,prior_one_offs=[],source_ref=ref(year))


def room(value):return annual_social_room(value,through=value['coverage_to'],section_key='regular')


class SocialOneOffTests(unittest.TestCase):
    def test_published_drv_february_entry_june_vacation_bonus(self):
        result=room(basis(2026,'2026-06-30',560000,first_month=2))
        self.assertEqual(result['branches']['health'],dict(sv_days=150,annual_cap_minor=6975000,
            partial_cap_minor=2906250,contributed_minor=2800000,room_minor=106250))
        self.assertEqual(result['branches']['pension']['partial_cap_minor'],4225000)
        selected=self.assign(result,receipt='2026-06-20',amount=150000,prior=False)
        self.assertEqual(selected['bases_minor'],dict(health=106250,care=106250,pension=150000,unemployment=150000))

    def assign(self,current,previous=None,receipt='2026-03-31',amount=243750,prior=True,mandatory=True):
        return select_one_off_assignment(receipt_date=receipt,amount_minor=amount,current_room=current,
            previous_room=previous,current_period_ref=ref(701) if current else None,
            previous_period_ref=ref(702) if previous else None,
            mandatory_statutory_health=mandatory,previous_year_employment=prior)

    def test_exact_march_room_and_one_cent_over_use_different_years(self):
        current=room(basis(2026,'2026-03-31',500000));previous=room(basis(2025,'2025-12-31',550000))
        exact=self.assign(current,previous)
        above=self.assign(current,previous,amount=243751)
        self.assertEqual((exact['social_year'],exact['march_clause']),(2026,False))
        self.assertEqual((above['tax_year'],above['social_year'],above['march_clause']),(2026,2025,True))
        self.assertEqual(above['bases_minor'],dict(health=15000,care=15000,pension=243751,unemployment=243751))

    def test_april_payment_after_march_exit_does_not_trigger_march_clause(self):
        current=room(basis(2026,'2026-03-31',500000));previous=room(basis(2025,'2025-12-31',550000))
        result=self.assign(current,previous,receipt='2026-04-01',amount=243751)
        self.assertEqual((result['social_year'],result['assigned_period_end'],result['march_clause']),(2026,'2026-03-31',False))
        self.assertEqual(result['bases_minor']['health'],243750)

    def test_pension_threshold_applies_when_no_statutory_health_obligation(self):
        current=room(basis(2026,'2026-03-31',500000));previous=room(basis(2025,'2025-12-31',550000))
        result=self.assign(current,previous,amount=243751,mandatory=False)
        self.assertEqual((result['decisive_branch'],result['social_year']),('pension',2026))

    def test_missing_previous_year_is_not_replaced_by_current_parameters(self):
        current=room(basis(2026,'2026-03-31',500000))
        with self.assertRaises(Problem):self.assign(current,amount=243751)
        result=self.assign(current,amount=243751,prior=False)
        self.assertEqual((result['social_year'],result['bases_minor']['health']),(2026,243750))

    def test_previous_year_departure_and_april_without_current_employment(self):
        previous=room(basis(2025,'2025-12-31',550000))
        march=self.assign(None,previous,amount=50000)
        april=self.assign(None,previous,receipt='2026-04-01',amount=50000)
        self.assertEqual((march['social_year'],march['bases_minor']['health']),(2025,15000))
        self.assertEqual(april['bases_minor'],dict(health=0,care=0,pension=0,unemployment=0))

    def test_prior_bonus_consumes_only_its_contributed_branch_bases(self):
        value=basis(2026,'2026-06-30',560000,first_month=2)
        value['prior_one_offs']=[dict(source_ref=ref(800),section_key='regular',assigned_period_end='2026-05-31',
            bases_minor=dict(health=50000,care=50000,pension=80000,unemployment=80000))]
        result=room(value)
        self.assertEqual((result['branches']['health']['room_minor'],result['branches']['pension']['room_minor']),
                         (56250,1345000))
        value['prior_one_offs'].append(copy.deepcopy(value['prior_one_offs'][0]))
        with self.assertRaises(Problem):room(value)

    def test_actual_partial_dates_and_continued_employment_are_distinguished(self):
        value=basis(2026,'2026-01-31',100000)
        for item in value['periods'][0]['branches'].values():
            item['eligible_intervals'][0].update(start='2026-01-16',legal_reason='continued_section_7_3')
        result=room(value)
        self.assertEqual(result['branches']['pension']['sv_days'],16)
        self.assertEqual(result['branches']['pension']['partial_cap_minor'],450667)
        self.assertEqual(result['branches']['health']['partial_cap_minor'],310000)

    def test_two_profile_parts_do_not_duplicate_a_full_calendar_month(self):
        value=basis(2026,'2026-01-31',100000);second=copy.deepcopy(value['periods'][0])
        first=value['periods'][0];first['end']='2026-01-15';second['start']='2026-01-16';second['part_key']='changed-fund'
        for branch in first['branches'].values():branch['eligible_intervals'][0]['end']=first['end']
        for branch in second['branches'].values():branch['eligible_intervals'][0]['start']=second['start']
        value['periods'].append(second)
        self.assertEqual(room(value)['branches']['health']['sv_days'],30)
        self.assertEqual(room(value)['branches']['health']['partial_cap_minor'],581250)

    def test_duplicate_or_incomplete_period_sources_are_rejected(self):
        value=basis(2026,'2026-03-31',500000)
        value['periods'].append(copy.deepcopy(value['periods'][0]))
        with self.assertRaises(Problem):room(value)
        value=basis(2026,'2026-03-31',500000)
        with self.assertRaises(Problem):annual_social_room(value,through='2026-04-30',section_key='regular')
        value['periods'][0]['branches']['health']['eligible_intervals']=[]
        with self.assertRaises(Problem):room(value)

    def test_status_section_and_legal_employer_cannot_be_merged(self):
        current=room(basis(2026,'2026-03-31',500000));previous=room(basis(2025,'2025-12-31',550000))
        previous['employer_key']='different-legal-employer'
        with self.assertRaises(Problem):self.assign(current,previous,amount=243751)
        value=basis(2026,'2026-03-31',500000);value['periods'][0]['section_key']='minijob'
        self.assertEqual(room(value)['branches']['health']['sv_days'],60)

    def test_published_minijob_600_plus_300_example_requires_midijob(self):
        months=[]
        for month in range(1,13):
            earnings=[dict(source_ref=ref(900),amount_minor=60000,kind='running')]
            if month==6:earnings.append(dict(source_ref=ref(901),amount_minor=30000,kind='foreseeable_one_off'))
            months.append(dict(month=f'2026-{month:02}',earnings=earnings,source_ref=ref(950+month)))
        result=classify_regular_pay(year=2026,months=months)
        self.assertEqual((result['forecast_total_minor'],result['monthly_average_minor'],result['classification']),
                         (750000,62500,'midijob'))

    def test_forecast_classification_compares_unrounded_average(self):
        months=[dict(month=f'2026-{m:02}',earnings=[dict(source_ref=ref(1),amount_minor=60300,kind='running')],source_ref=ref(m)) for m in range(1,13)]
        self.assertEqual(classify_regular_pay(year=2026,months=months)['classification'],'minijob')
        months[-1]['earnings'][0]['amount_minor']+=1
        result=classify_regular_pay(year=2026,months=months)
        self.assertEqual((result['monthly_average_minor'],result['classification']),(60300,'midijob'))

    def test_midijob_upper_boundary_and_no_pay_comparison(self):
        below=transition_bases(year=2026,actual_minor=200000)
        above=transition_bases(year=2026,actual_minor=200001)
        self.assertEqual((below['total_minor'],below['employee_minor'],below['method']),(200000,200000,'transition'))
        self.assertEqual((above['total_minor'],above['employee_minor'],above['method']),(200001,200001,'above_upper_bound'))
        absent=transition_bases(year=2026,actual_minor=85000,comparison_minor=215000)
        self.assertEqual((absent['total_minor'],absent['employee_minor']),(85000,85000))
        with self.assertRaises(Problem):transition_bases(year=2026,actual_minor=200001,comparison_minor=200000)

    def test_actual_2025_transition_factor_and_final_cent_rounding(self):
        # Below the lower boundary the source rule is AE*F; employee base is zero.
        old=transition_bases(year=2025,actual_minor=50000)
        new=transition_bases(year=2026,actual_minor=50000)
        self.assertEqual((old['total_minor'],new['total_minor']),(33415,33095))
        self.assertEqual((old['employee_minor'],new['employee_minor']),(0,0))


def historical_profile(**changes):
    return dict(source_ref=ref(800),health_additional_percent='2.90',saxony=False,
        childless_surcharge=True,care_child_discounts=0)|changes


class OneOffContributionTests(unittest.TestCase):
    def test_published_room_example_has_separate_branch_contributions_and_no_u1_u2(self):
        current=room(basis(2026,'2026-06-30',560000,first_month=2))
        assignment=select_one_off_assignment(receipt_date='2026-06-20',amount_minor=150000,
            current_room=current,previous_room=None,current_period_ref=ref(701),previous_period_ref=None,
            mandatory_statutory_health=True,previous_year_employment=False)
        result=calculate_regular_one_off_contributions(assignment=assignment,profile=historical_profile())
        self.assertEqual(result['employee_contributions'],dict(health_general=7756,health_additional=1541,
            pension=13950,unemployment=1950,care=2551))
        self.assertEqual(result['employer_contributions'],dict(health_general=7756,health_additional=1541,
            pension=13950,unemployment=1950,care=1913))
        self.assertEqual(result['employer_levies'],dict(u1=0,u2=0,insolvency=225))

    def test_actual_2025_fund_and_saxony_child_discount_are_not_replaced_by_2026_defaults(self):
        branches={key:dict(total_minor=100000,employee_minor=100000) for key in ('health','care','pension','unemployment')}
        old=assess_social_contributions(year=2025,branch_bases=branches,
            profile=historical_profile(health_additional_percent='1.70',saxony=True,
                                       childless_surcharge=False,care_child_discounts=2))
        self.assertEqual(old['employee_contributions'],dict(health_general=7300,health_additional=850,
            pension=9300,unemployment=1300,care=1800))
        self.assertEqual(old['employer_contributions']['care'],1300)
        self.assertEqual(old['care_adjustments']['children_discount_minor'],500)
        self.assertEqual(old['insolvency_minor'],150)

    def test_reduced_pv_uses_total_for_surcharge_and_employee_for_child_discount(self):
        branches={key:dict(total_minor=50000,employee_minor=20000) for key in ('health','care','pension','unemployment')}
        childless=assess_social_contributions(year=2026,branch_bases=branches,
            profile=historical_profile(),reduced=True)
        parent=assess_social_contributions(year=2026,branch_bases=branches,
            profile=historical_profile(childless_surcharge=False,care_child_discounts=2),reduced=True)
        self.assertEqual((childless['employee_contributions']['care'],childless['employer_contributions']['care']),(660,1440))
        self.assertEqual((parent['employee_contributions']['care'],parent['employer_contributions']['care']),(260,1440))

    def test_bonus_crossing_transition_upper_limit_reassesses_running_levies_only(self):
        profile=historical_profile();before_base=transition_bases(year=2026,actual_minor=190000)
        prior=assess_social_contributions(year=2026,
            branch_bases={key:{k:before_base[k] for k in ('total_minor','employee_minor')}
                          for key in ('health','care','pension','unemployment')},profile=profile,reduced=True)
        result=reassess_transition_one_off(year=2026,running_minor=190000,bonus_minor=20000,
            profile=profile,u1_percent='2.000',u2_percent='0.300',original_assessment=prior)
        self.assertEqual(result['transition_after']['total_minor'],210000)
        self.assertEqual(result['u1_u2_ongoing_basis_after_minor'],190000)
        self.assertEqual(result['employer_levies']['u1'],29)
        self.assertEqual(result['employer_levies']['u2'],4)
        self.assertEqual(result['after']['employee_contributions'],dict(health_general=15330,health_additional=3045,
            pension=19530,unemployment=2730,care=5040))
        broken=copy.deepcopy(prior);broken['employee_contributions']['pension']+=1
        with self.assertRaises(Problem):reassess_transition_one_off(year=2026,running_minor=190000,
            bonus_minor=20000,profile=profile,u1_percent='2',u2_percent='0.3',original_assessment=broken)

    def test_bonus_under_minijob_minimum_does_not_charge_minimum_a_second_time(self):
        result=calculate_minijob_one_off_contributions(year=2026,running_bases=dict(health=10000,pension=10000),
            bonus_bases=dict(health=5000,pension=5000),bonus_minor=5000,minimum_pension_basis_minor=17500,
            statutory_health=True,rv_exempt=False,pension_other_compulsory=False,profile_ref=ref(8))
        self.assertEqual((result['before']['employee_pension_minor'],result['after']['employee_pension_minor'],
                          result['employee_pension_minor']),(1755,1005,-750))
        self.assertEqual((result['employer_health_minor'],result['employer_pension_minor'],
                          result['employer_flat_tax_minor']),(650,750,100))
        self.assertEqual(result['employer_levies'],dict(u1=0,u2=0,insolvency=8))

    def test_exempt_private_minijob_has_no_employee_pension_or_health_flat_contribution(self):
        result=calculate_minijob_one_off_contributions(year=2025,running_bases=dict(health=50000,pension=50000),
            bonus_bases=dict(health=10000,pension=10000),bonus_minor=10000,minimum_pension_basis_minor=17500,
            statutory_health=False,rv_exempt=True,pension_other_compulsory=False,profile_ref=ref(8))
        self.assertEqual((result['employee_pension_minor'],result['employer_health_minor'],
                          result['employer_pension_minor'],result['employer_flat_tax_minor']),(0,0,1500,200))

    def history(self,used=()):
        months=['2025-12']+[f'2026-{month:02}' for month in range(1,11)]
        return [dict(month=value,exception_used=value in used,source_ref=ref(index+1)) for index,value in enumerate(months)]

    def test_second_unforeseen_month_at_1206_is_allowed_but_third_and_next_cent_are_not(self):
        def assess(amount=120600,used=('2026-01',)):
            return assess_minijob_unforeseen_month(year=2026,month='2026-11',total_minor=amount,
                annual_limit_exceeded=True,unforeseen=True,history=self.history(used),source_ref=ref(99))
        self.assertTrue(assess()['remains_minijob'])
        self.assertFalse(assess(120601)['remains_minijob'])
        self.assertFalse(assess(used=('2026-01','2026-04'))['remains_minijob'])
        self.assertEqual(assess()['previous_exception_months'],1)

    def test_foreseeable_bonus_and_explicit_rolling_month_completeness_are_separate(self):
        args=dict(year=2026,month='2026-11',total_minor=90000,annual_limit_exceeded=True,
            unforeseen=False,history=self.history(),source_ref=ref(99))
        self.assertFalse(assess_minijob_unforeseen_month(**args)['remains_minijob'])
        self.assertFalse(assess_minijob_unforeseen_month(**(args|dict(annual_limit_exceeded=False)))['exception_used'])
        with self.assertRaises(Problem):assess_minijob_unforeseen_month(**(args|dict(history=self.history()[1:])))
        wrong=self.history();wrong[0]['month']='2025-11'
        with self.assertRaises(Problem):assess_minijob_unforeseen_month(**(args|dict(history=wrong)))


if __name__=='__main__':unittest.main()
