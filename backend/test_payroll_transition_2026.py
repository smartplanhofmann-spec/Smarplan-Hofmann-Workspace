"""Independent DRV 2026 base table and GKV care-contribution reference.

Expected component cents below are manually calculated legal examples, not
generated with the implementation. BMF class-VI tax uses PAP p39 annual table.
"""
import json
import unittest

from core import Problem
from payroll_de_2026 import calculate,normalize_profile,RULE_VERSION,FULL_RULE_VERSION
from payroll_transition_2026 import assessment_bases,care_contributions,TRANSITION_RULE_VERSION
from test_payroll_de_2026 import profile

DRV_BASES=((60301,39914,1),(70000,51028,13887),(80000,62488,28203),
    (100000,85406,56836),(120000,108325,85469),(140000,131244,114102),
    (160000,154163,142734),(180000,177081,171367),(200000,200000,200000))


def assessment(amount=100000,**changes):
    return dict(status='within_transition_area',assessed_on='2026-01-01',regular_monthly_gross_minor=amount,
        forecast_months=12,foreseeable_one_off_payments=False,note='Synthetic reviewed 12-month contract and hours prognosis')|changes


def transition_profile(amount=100000,**changes):
    return profile('regular',regular_annual_gross_minor=amount*12,health_additional_percent='2.90',
        tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0,transition_assessment=assessment(amount))|changes


class Transition2026Tests(unittest.TestCase):
    def calc(self,gross=100000,**changes):
        return calculate(transition_profile(**changes),'2026-10',gross,full_month_confirmed=True)

    def test_all_nine_official_drv_2026_assessment_pairs(self):
        for gross,total,employee in DRV_BASES:
            with self.subTest(gross=gross):
                bases=assessment_bases(gross)
                self.assertEqual((bases['total_assessment_minor'],bases['employee_assessment_minor']),(total,employee))
        # Published DRV 2026 800-EUR pension example: 116.22 total, AN26.23.
        result=self.calc(80000)
        self.assertEqual(result['employee_contributions']['pension'],2623)
        self.assertEqual(result['employer_contributions']['pension'],8999)

    def test_exact_independent_1000_euro_components_levies_and_net(self):
        result=self.calc()
        self.assertEqual(result['employee_contributions'],dict(health_general=4149,health_additional=824,pension=5286,unemployment=739,care=1535))
        self.assertEqual(result['employer_contributions'],dict(health_general=8321,health_additional=1652,pension=10600,unemployment=1481,care=2051))
        self.assertEqual(result['employee_social_total_minor'],12533)
        self.assertEqual(result['employer_social_total_minor'],24105)
        self.assertEqual(result['employer_levies'],dict(u1=1794,u2=376,insolvency=128))
        self.assertEqual(result['net_minor'],87467)
        self.assertEqual(result['employer_total_excluding_accident_insurance_minor'],126403)
        self.assertEqual(result['rule_version'],TRANSITION_RULE_VERSION)
        self.assertFalse(result['official_system_approval'])
        self.assertEqual(result['statutory_report_status'],'not_transmitted')

    def test_forecast_election_and_actual_month_thresholds_are_distinct(self):
        for gross,total,employee,regime in ((60300,39913,0,'below_or_at_lower_limit'),
                (60301,39914,1,'within_transition_area'),(200000,200000,200000,'within_transition_area'),
                (200001,200001,200001,'above_upper_limit')):
            with self.subTest(gross=gross):
                result=self.calc(gross)
                self.assertTrue(result['payroll_calculation_complete'])
                self.assertEqual(result['transition']['regime'],regime)
                self.assertEqual(result['transition']['regular_monthly_gross_minor'],100000)
                self.assertEqual(result['transition']['total_assessment_minor'],total)
                self.assertEqual(result['transition']['employee_assessment_minor'],employee)
        low=self.calc(10000)
        self.assertEqual(low['employee_contributions'],dict(health_general=0,health_additional=0,pension=0,unemployment=0,care=40))
        self.assertEqual(low['employer_contributions'],dict(health_general=966,health_additional=192,pension=1232,unemployment=172,care=238))
        self.assertEqual(low['net_minor'],9960)
        high=self.calc(900000)
        self.assertEqual(high['transition']['branch_bases']['health_general'],dict(total_minor=581250,employee_minor=581250))
        self.assertEqual(high['transition']['branch_bases']['pension'],dict(total_minor=845000,employee_minor=845000))

    def test_gkv_published_care_example_and_children_do_not_raise_employer_contribution(self):
        # GKV 31.03.2025 3.3 p12/13 uses 2025 bases 815.90 /545.71:
        # total29.38, theoretical AN9.82, AG19.56, discount1.36, AN8.46.
        employee,employer,proof=care_contributions(81590,54571,saxony=False,surcharge=False,discount_count=1,reduced=True)
        self.assertEqual((employee,employer),(846,1956))
        self.assertEqual(proof['children_discount_minor'],136)
        for children,expected in ((1,1023),(2,881),(3,739),(4,597),(5,455),(6,455)):
            with self.subTest(children=children):
                result=self.calc(has_children=True,pv_children_under_25=children)
                self.assertEqual(result['employee_contributions']['care'],expected)
                self.assertEqual(result['employer_contributions']['care'],2051)
        saxony=self.calc(federal_state='SN')
        self.assertEqual((saxony['employee_contributions']['care'],saxony['employer_contributions']['care']),(1819,1767))
        saxony_parent=self.calc(federal_state='SN',has_children=True,pv_children_under_25=2)
        self.assertEqual((saxony_parent['employee_contributions']['care'],saxony_parent['employer_contributions']['care']),(1165,1767))

    def test_childless_age_boundary_and_explicit_fund_levies(self):
        birthday=self.calc(date_of_birth='2003-10-02')
        self.assertFalse(birthday['care_childless_surcharge'])
        self.assertEqual(birthday['employee_contributions']['care'],1023)
        previous=self.calc(date_of_birth='2003-10-01')
        self.assertTrue(previous['care_childless_surcharge'])
        levy=self.calc(u1_required=False,u1_percent='0',u2_percent='0.37',health_additional_percent='3.10')
        self.assertEqual(levy['employer_levies'],dict(u1=0,u2=316,insolvency=128))
        self.assertEqual(levy['employee_contributions']['health_additional'],881)
        self.assertEqual(levy['employer_contributions']['health_additional'],1767)

    def test_class_vi_tax_uses_actual_gross_and_official_pap_reference(self):
        result=self.calc(125000,tax_class=6,church_tax='standard')
        # Official annual 15000 EUR /VI gives1676 EUR; monthly truncation.
        self.assertEqual(result['individual_wage_tax_minor'],13966)
        self.assertEqual(result['solidarity_minor'],0)
        self.assertEqual(result['church_tax_minor'],1256)
        self.assertEqual(result['employee_social_total_minor'],20274)
        self.assertEqual(result['net_minor'],89504)

    def test_explicit_atomic_profile_and_unsupported_cases(self):
        for update in ({'regular_monthly_gross_minor':60300},{'regular_monthly_gross_minor':200001},
                {'forecast_months':True},{'forecast_months':11},{'status':'automatic'},
                {'assessed_on':'2026-02-30'},{'note':''},{'foreseeable_one_off_payments':0}):
            with self.subTest(update=update),self.assertRaises(Problem):
                normalize_profile(transition_profile(transition_assessment=assessment(**update)))
        value=transition_profile();del value['transition_assessment']['note']
        with self.assertRaises(Problem):normalize_profile(value)
        for changes in ({'special_cases':['multiple_employments']},{'health_insurance':'private'},
                {'transition_assessment':assessment(foreseeable_one_off_payments=True)}):
            result=self.calc(**changes)
            self.assertFalse(result['payroll_calculation_complete']);self.assertIsNone(result['net_minor'])
        for month,full in (('2027-01',True),('2026-10',False)):
            self.assertFalse(calculate(transition_profile(),month,100000,full_month_confirmed=full)['payroll_calculation_complete'])

    def test_existing_rule_versions_never_opt_in_or_reinterpret_new_profile(self):
        old=profile('regular',regular_annual_gross_minor=1200000,tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        original=json.dumps(calculate(old,'2026-10',100000,full_month_confirmed=True),sort_keys=True)
        self.assertIn('transition_not_supported',original)
        self.calc()
        self.assertEqual(json.dumps(calculate(old,'2026-10',100000,full_month_confirmed=True),sort_keys=True),original)
        for version in (RULE_VERSION,FULL_RULE_VERSION):
            with self.assertRaises(Problem):calculate(transition_profile(),'2026-10',100000,full_month_confirmed=True,rule_version=version)
        with self.assertRaises(Problem):calculate(old,'2026-10',100000,full_month_confirmed=True,rule_version=TRANSITION_RULE_VERSION)


if __name__=='__main__':unittest.main()
