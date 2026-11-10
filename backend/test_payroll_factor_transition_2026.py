"""Independent DRV bases and separate pinned XML factor-tax expectations."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from core import Problem
from payroll_de_2026 import calculate
from payroll_factor_transition_2026 import calculate_factor_transition, RULE_VERSION, SCOPE
from test_payroll_factor_2026 import factor_profile
from test_payroll_transition_2026 import assessment, DRV_BASES


def inputs(gross=200000, **changes):
    profile=factor_profile(regular_annual_gross_minor=gross*12,**changes)
    return dict(profile=profile,assessment=assessment(gross),month='2026-10',
                gross_minor=gross,full_month_confirmed=True)


class FactorTransitionKernel(unittest.TestCase):
    def test_independent_drv_bases_and_actual_low_wage_factor_case(self):
        for gross,total,employee in DRV_BASES:
            with self.subTest(gross=gross):
                result=calculate_factor_transition(**inputs(gross))
                self.assertTrue(result['payroll_calculation_complete'])
                self.assertEqual(result['scope'],SCOPE)
                self.assertEqual(result['rule_version'],RULE_VERSION)
                self.assertEqual(result['transition']['total_assessment_minor'],total)
                self.assertEqual(result['transition']['employee_assessment_minor'],employee)
                self.assertFalse(result['official_system_approval'])
                self.assertEqual(result['statutory_report_status'],'not_transmitted')
        result=calculate_factor_transition(**inputs(100000))
        self.assertEqual(result['employee_contributions'],dict(health_general=4149,
            health_additional=824,pension=5286,unemployment=739,care=1535))
        self.assertEqual(result['employer_contributions'],dict(health_general=8321,
            health_additional=1652,pension=10600,unemployment=1481,care=2051))
        self.assertEqual(result['net_minor'],87467)
        self.assertEqual(result['employer_levies'],dict(u1=1794,u2=376,insolvency=128))
        self.assertEqual(result['employer_total_excluding_accident_insurance_minor'],126403)

    def test_every_tax_reference_executes_separate_xml_not_this_calculator(self):
        proof=json.loads((Path(__file__).parent/'testdata/payroll_factor_transition_2026.json').read_text())
        self.assertFalse(proof['production_kernel_imported'])
        self.assertEqual(proof['xml_sha256'],'63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4')
        self.assertEqual(len(proof['cases']),32)
        for row in proof['cases']:
            p=row['input'];has_children=not p['childless_surcharge']
            args=inputs(p['gross_minor'],tax_factor=p['factor'],
                tax_children_half_units=p['children_half_units'],
                federal_state='SN' if p['saxony'] else 'HE',
                church_tax='standard' if p['church_member'] else 'none',
                health_additional_percent=p['additional_health_percent'],
                has_children=has_children,pv_children_under_25=p['care_child_discounts']+1 if has_children else 0)
            with self.subTest(tax_input=p):
                result=calculate_factor_transition(**args);expected=row['expected']
                self.assertEqual(result['individual_wage_tax_minor'],expected['LSTLZZ'])
                self.assertEqual(result['solidarity_minor'],expected['SOLZLZZ'])
                self.assertEqual(result['tax_parameters']['church_assessment_minor'],expected['BK'])
                church=expected['BK']*9//100 if p['church_member'] else 0
                self.assertEqual(result['church_tax_minor'],church)
                self.assertEqual(result['net_minor'],p['gross_minor']-result['employee_social_total_minor']-sum((expected['LSTLZZ'],expected['SOLZLZZ'],church)))

    def test_actual_profile_and_separate_prognosis_are_preserved(self):
        args=inputs();original=deepcopy(args)
        historical=calculate(args['profile'],'2026-10',200000,full_month_confirmed=True)
        self.assertFalse(historical['payroll_calculation_complete'])
        result=calculate_factor_transition(**args)
        self.assertTrue(result['payroll_calculation_complete'])
        self.assertEqual(args,original)
        self.assertNotIn('transition_assessment',args['profile'])
        component=result['factor_transition_components']
        self.assertEqual(component['assessment'],args['assessment'])
        self.assertEqual(component['contribution_profile']['transition_assessment'],args['assessment'])
        self.assertNotIn('tax_factor',component['contribution_profile'])
        self.assertEqual(calculate(args['profile'],'2026-10',200000,full_month_confirmed=True),historical)

    def test_unsupported_sources_and_other_cases_never_produce_a_net(self):
        variants=[dict(month='2027-10'),dict(full_month_confirmed=False),
            dict(source_issues=['wage_source_mismatch']),dict(gross_minor=199999),
            dict(profile=inputs()['profile']|dict(health_insurance='private')),
            dict(profile=inputs()['profile']|dict(special_cases=['tax_factor','one_off_payment'])),
            dict(profile=inputs()['profile']|dict(effective_from='2026-10-02')),
            dict(assessment=assessment(200000,foreseeable_one_off_payments=True)),
            dict(assessment=assessment(200000,assessed_on='2026-10-02'))]
        for replacement in variants:
            with self.subTest(replacement=replacement):
                result=calculate_factor_transition(**(inputs()|replacement))
                self.assertFalse(result['payroll_calculation_complete'])
                self.assertFalse(result['social_contributions_available'])
                self.assertEqual(result['scope'],'unsupported')
                self.assertIsNone(result['net_minor'])
                self.assertIsNone(result['employee_social_total_minor'])
                self.assertTrue(result['blockers'])

    def test_factor_and_prognosis_must_be_explicit_consistent_normalized_values(self):
        args=inputs()
        variants=[dict(profile={k:v for k,v in args['profile'].items()if k!='tax_factor'}),
            dict(profile=args['profile']|dict(tax_factor='0.75')),
            dict(profile=args['profile']|dict(tax_class=1)),
            dict(profile=args['profile']|dict(tax_allowance_monthly_minor=1)),
            dict(profile=args['profile']|dict(transition_assessment=args['assessment'])),
            dict(assessment=None),dict(assessment=assessment(199999)),
            dict(assessment=assessment(200000,forecast_months=11)),
            dict(assessment=assessment(200000,foreseeable_one_off_payments=1)),
            dict(full_month_confirmed=1),dict(rule_version='de_2026_standard_factor_monthly_v8')]
        for replacement in variants:
            with self.subTest(replacement=replacement),self.assertRaises(Problem):
                calculate_factor_transition(**(args|replacement))

    def test_zero_factor_and_church_state_rate_are_actual_explicit_choices(self):
        zero=calculate_factor_transition(**inputs(tax_factor='0.000',church_tax='standard'))
        self.assertEqual(zero['individual_wage_tax_minor'],0)
        self.assertEqual(zero['church_tax_minor'],0)
        he=calculate_factor_transition(**inputs(church_tax='standard',federal_state='HE'))
        by=calculate_factor_transition(**inputs(church_tax='standard',federal_state='BY'))
        self.assertGreater(he['individual_wage_tax_minor'],0)
        self.assertEqual(he['employee_contributions'],by['employee_contributions'])
        self.assertEqual(he['church_tax_minor'],he['tax_parameters']['church_assessment_minor']*9//100)
        self.assertEqual(by['church_tax_minor'],by['tax_parameters']['church_assessment_minor']*8//100)


if __name__=='__main__':unittest.main()
