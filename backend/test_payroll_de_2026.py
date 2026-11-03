"""Primary-source minijob examples and independently derived SV boundaries.

150 EUR and 25 EUR are the Minijob-Zentrale's actual published RV examples.
Other expected amounts are independent arithmetic from the cited 2026 rates,
not results copied from this engine or a claimed live BMF comparison.
"""
import unittest
from core import Problem
from payroll_de_2026 import calculate, normalize_profile, RULES_SHA256, RULE_VERSION


def profile(kind='minijob',**changes):
    result=dict(effective_from='2026-01-01',employment_kind=kind,date_of_birth='1990-02-01',federal_state='HE',
        tax_class=1,tax_children_half_units=0,church_tax='none',health_insurance='statutory_mandatory',
        health_fund='Synthetic documented fund',health_additional_percent='2.69',has_children=False,pv_children_under_25=0,
        u1_required=True,u1_percent='0.80' if kind=='minijob' else '2.10',u2_percent='0.22' if kind=='minijob' else '0.44',
        minijob_rv_exempt=False,minijob_tax='flat_2_employer' if kind=='minijob' else 'individual',
        pension_other_compulsory=False,regular_annual_gross_minor=723600 if kind=='minijob' else 4200000,
        special_cases=[],verification_note='Synthetic verified source values for reference tests')
    result.update(changes)
    return result


class Payroll2026ReferenceTests(unittest.TestCase):
    def mini(self,amount,**changes):
        return calculate(profile(**changes),'2026-10',amount,full_month_confirmed=True)

    def regular(self,amount=350000,**changes):
        return calculate(profile('regular',**changes),'2026-10',amount,full_month_confirmed=True)

    def test_official_150_euro_minimum_contribution_example(self):
        result=self.mini(15000)
        self.assertEqual(result['employer_contributions']['pension'],2250)
        self.assertEqual(result['employee_contributions']['pension'],1005)
        self.assertEqual(result['net_minor'],13995)
        self.assertTrue(result['payroll_calculation_complete'])

    def test_official_25_euro_example_requires_employee_top_up(self):
        result=self.mini(2500)
        self.assertEqual(result['employer_contributions']['pension'],375)
        self.assertEqual(result['employee_contributions']['pension'],2880)
        self.assertEqual(result['net_minor'],-380)
        self.assertEqual(result['payout_minor'],0)
        self.assertEqual(result['employee_additional_payment_minor'],380)

    def test_603_euro_components_are_rounded_individually(self):
        result=self.mini(60300)
        self.assertEqual(result['employee_social_total_minor'],2171)
        self.assertEqual(result['employer_contributions']['health_general'],7839)
        self.assertEqual(result['employer_contributions']['pension'],9045)
        self.assertEqual(result['employer_levies'],dict(u1=482,u2=133,insolvency=90))
        self.assertEqual(result['employer_flat_tax_minor'],1206)
        self.assertEqual(result['net_minor'],58129)
        # A single combined 31.17% calculation would incorrectly add one cent.
        self.assertEqual(result['employer_total_excluding_accident_insurance_minor'],79095)
        self.assertFalse(result['accident_insurance_included'])
        self.assertEqual(result['rules_sha256'],RULES_SHA256)

    def test_pension_exemption_private_health_and_minimum_exception_are_explicit(self):
        result=self.mini(15000,minijob_rv_exempt=True,health_insurance='private')
        self.assertEqual(result['net_minor'],15000)
        self.assertEqual(result['employer_contributions']['health_general'],0)
        self.assertEqual(result['employer_contributions']['pension'],2250)
        excepted=self.mini(15000,pension_other_compulsory=True)
        self.assertEqual(excepted['employee_contributions']['pension'],540)
        self.assertEqual(excepted['net_minor'],14460)

    def test_regular_contributions_never_invent_a_tax_or_net_result(self):
        result=self.regular()
        self.assertEqual(result['employee_contributions'],dict(health_general=25550,health_additional=4708,pension=32550,unemployment=4550,care=8400))
        self.assertEqual(result['employee_social_total_minor'],75758)
        self.assertEqual(result['employer_social_total_minor'],73658)
        self.assertEqual(result['employer_total_excluding_accident_insurance_minor'],433073)
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertTrue(result['social_contributions_available'])
        for field in ('individual_wage_tax_minor','solidarity_minor','church_tax_minor','net_minor','payout_minor'):
            self.assertIsNone(result[field])
        self.assertEqual(result['blockers'][0]['code'],'tax_profile_incomplete')

    def test_historical_v1_calculation_retains_exact_rules_and_original_missing_pap_reason(self):
        result=calculate(profile('regular'),'2026-10',350000,full_month_confirmed=True,rule_version=RULE_VERSION)
        self.assertEqual(result['rule_version'],RULE_VERSION)
        self.assertEqual(result['rules_sha256'],RULES_SHA256)
        self.assertNotIn('pap_version',result)
        self.assertEqual(result['blockers'][0]['code'],'official_pap_not_validated')
        self.assertIsNone(result['net_minor'])
        with self.assertRaises(Problem):
            calculate(profile('regular'),'2026-10',350000,full_month_confirmed=True,rule_version='future_unknown')

    def test_health_additional_contribution_is_separately_rounded(self):
        result=self.regular(200006)
        self.assertEqual(result['employee_contributions']['health_general'],14600)
        self.assertEqual(result['employee_contributions']['health_additional'],2690)
        self.assertEqual(sum(result['employee_contributions'][key] for key in ('health_general','health_additional')),17290)

    def test_saxony_parenthood_and_children_discount_have_separate_shares(self):
        saxony=self.regular(federal_state='SN')
        self.assertEqual(saxony['employee_contributions']['care'],10150)
        self.assertEqual(saxony['employer_contributions']['care'],4550)
        parent=self.regular(has_children=True,pv_children_under_25=0)
        self.assertEqual(parent['employee_contributions']['care'],6300)
        many=self.regular(has_children=True,pv_children_under_25=6)
        self.assertEqual(many['employee_contributions']['care'],2800)
        self.assertEqual(many['care_discount_children'],4)
        two=self.regular(has_children=True,pv_children_under_25=2)
        self.assertEqual(two['employee_contributions']['care'],5425)

    def test_23rd_year_completion_changes_surcharge_only_at_the_legal_month_boundary(self):
        first_day=self.regular(date_of_birth='2003-10-01')
        later_day=self.regular(date_of_birth='2003-10-02')
        self.assertTrue(first_day['care_childless_surcharge'])
        self.assertFalse(later_day['care_childless_surcharge'])
        november=calculate(profile('regular',date_of_birth='2003-10-02'),'2026-11',350000,full_month_confirmed=True)
        self.assertTrue(november['care_childless_surcharge'])

    def test_health_cap_and_church_parameters_are_recorded_without_tax_estimates(self):
        result=self.regular(600000,regular_annual_gross_minor=7200000,church_tax='standard',federal_state='BY',tax_children_half_units=3)
        self.assertEqual(result['employee_contributions']['health_general'],42431)
        self.assertEqual(result['employee_contributions']['health_additional'],7818)
        self.assertEqual(result['employee_contributions']['care'],13950)
        self.assertEqual(result['tax_parameters'],dict(tax_class=1,children_half_units=3,church_tax_percent='8'))
        self.assertIsNone(result['church_tax_minor'])

    def test_unsupported_classification_and_special_cases_produce_no_fake_zero_net(self):
        cases=[self.mini(60301),self.regular(200000),self.regular(300000,health_insurance='private'),
               self.mini(60300,special_cases=['multiple_employments']),self.mini(60300,minijob_tax='individual'),
               self.mini(60300,u2_percent='0.24'),self.regular(600000,regular_annual_gross_minor=9000000),
               calculate(profile(),'2027-01',60300,full_month_confirmed=True),
               calculate(profile(),'2026-10',60300,full_month_confirmed=False)]
        for result in cases:
            with self.subTest(issues=result['blockers']):
                self.assertFalse(result['social_contributions_available'])
                self.assertIsNone(result['net_minor'])
                self.assertIsNone(result['employee_social_total_minor'])

    def test_strict_types_reject_missing_parameters_floats_booleans_and_inconsistent_children(self):
        malformed=[profile(health_additional_percent=2.69),profile(tax_class=True),profile(federal_state=[]),
                   profile(has_children=False,pv_children_under_25=2),{key:value for key,value in profile().items() if key!='health_additional_percent'}]
        for value in malformed:
            with self.subTest(value=value),self.assertRaises(Problem):
                normalize_profile(value)
        with self.assertRaises(Problem):
            self.mini(60300.0)
        with self.assertRaises(Problem):
            self.mini(True)

    def test_regular_monthly_net_uses_official_annual_table_and_separate_sv_rounding(self):
        # BMF Anlage 1 p39, 60000 EUR annual, KVZ=2.90; tax-II PVZ=0.
        annual_tax=(938900,809100,482200,938900,1536400,1589500)
        for tax_class,annual_minor in enumerate(annual_tax,1):
            result=self.regular(500000,regular_annual_gross_minor=6000000,
                health_additional_percent='2.90',tax_class=tax_class,
                has_children=tax_class==2,tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
            with self.subTest(tax_class=tax_class):
                self.assertEqual(result['scope'],'regular_standard_monthly')
                self.assertTrue(result['payroll_calculation_complete'])
                self.assertEqual(result['individual_wage_tax_minor'],annual_minor//12)
                # 365+72.50+465+65+120 (II:90) EUR, independently from rates.
                social=105750 if tax_class==2 else 108750
                self.assertEqual(result['employee_social_total_minor'],social)
                self.assertEqual(result['net_minor'],500000-social-annual_minor//12)
                self.assertEqual(result['payout_minor'],result['net_minor'])
                self.assertEqual(result['solidarity_minor'],0)
                self.assertEqual(result['church_tax_minor'],0)
                self.assertEqual(result['blockers'],[])

    def test_regular_church_withholding_truncates_each_month_and_children_only_change_assessment(self):
        common=dict(regular_annual_gross_minor=6000000,health_additional_percent='2.90',
            tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0,church_tax='standard')
        bavaria=self.regular(500000,federal_state='BY',**common)
        hesse=self.regular(500000,federal_state='HE',**common)
        # 782.41 EUR official monthly measure: 8%=62.5928, 9%=70.4169 EUR.
        self.assertEqual(bavaria['church_tax_minor'],6259)
        self.assertEqual(hesse['church_tax_minor'],7041)
        child=self.regular(500000,federal_state='BY',tax_children_half_units=2,**common)
        self.assertEqual(child['individual_wage_tax_minor'],bavaria['individual_wage_tax_minor'])
        self.assertLess(child['tax_parameters']['church_assessment_minor'],bavaria['tax_parameters']['church_assessment_minor'])
        self.assertEqual(child['church_tax_minor'],child['tax_parameters']['church_assessment_minor']*8//100)

    def test_regular_allowance_and_addition_are_explicit_and_affect_only_tax(self):
        base=dict(regular_annual_gross_minor=6000000,health_additional_percent='2.90',
            tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        result=self.regular(500000,**base)
        lower=self.regular(500000,**{**base,'tax_allowance_monthly_minor':20000})
        higher=self.regular(500000,**{**base,'tax_addition_monthly_minor':20000})
        self.assertLess(lower['individual_wage_tax_minor'],result['individual_wage_tax_minor'])
        self.assertGreater(higher['individual_wage_tax_minor'],result['individual_wage_tax_minor'])
        self.assertEqual(lower['employee_contributions'],higher['employee_contributions'])
        self.assertEqual(lower['net_minor']-result['net_minor'],result['employee_tax_minor']-lower['employee_tax_minor'])
        for changes in (dict(tax_addition_monthly_minor=True),dict(health_additional_percent='2.695'),
                dict(tax_class=5,tax_children_half_units=1),dict(tax_class=6,tax_addition_monthly_minor=1),
                dict(tax_class=2,has_children=False)):
            with self.subTest(changes=changes),self.assertRaises(Problem):
                self.regular(500000,**{**base,**changes})
        with self.assertRaises(Problem):
            self.regular(tax_allowance_monthly_minor=0)

    def test_age_allowance_and_religious_special_case_never_become_complete_tax_results(self):
        # 64th birthday before Jan 2026 already triggers ALTER1, even before 65.
        result=self.regular(date_of_birth='1961-12-31',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        self.assertTrue(result['social_contributions_available'])
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertIsNone(result['net_minor'])
        self.assertEqual(result['blockers'][0]['code'],'age_allowance_not_supported')
        special=self.regular(special_cases=['church_tax_special_case'],tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        self.assertFalse(special['payroll_calculation_complete'])
        self.assertIsNone(special['net_minor'])


if __name__=='__main__':
    unittest.main()
