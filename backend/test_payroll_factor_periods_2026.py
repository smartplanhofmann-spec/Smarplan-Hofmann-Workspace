"""Independent XML factors, frozen source periods and unchanged old rules."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from core import Problem
from payroll_de_2026 import calculate
from payroll_factor_periods_2026 import (build_factor_period_plan,calculate_factor_period_source,
    calculate_factor_period_tax,FACTOR_PERIOD_SCOPE,FACTOR_PERIOD_RULE_VERSION)
import test_payroll_periods_2026 as periods


def source(**changes):
    return periods.period_snapshot(tax_class=4,special_cases=['tax_factor'],tax_factor='0.753',**changes)


class FactorPeriods2026(unittest.TestCase):
    def test_independent_xml_components_and_actual_period_totals(self):
        data=json.loads(Path(__file__).with_name('testdata').joinpath('payroll_factor_periods_2026.json').read_text())
        self.assertEqual(len(data['cases']),200)
        self.assertEqual(data['xml_sha256'],'63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4')
        for row in data['cases']:
            with self.subTest(inputs=row['inputs']):
                result=calculate_factor_period_tax(**row['inputs'])
                self.assertEqual(result['component'],row['expected_component'])
                self.assertEqual(result['totals'],row['expected_totals'])

    def test_source_dates_quotient_original_factor_and_hashes_are_preserved(self):
        snapshot=source();before=deepcopy(snapshot);plan=build_factor_period_plan(snapshot)
        self.assertTrue(plan['can_calculate']);self.assertEqual(snapshot,before)
        self.assertEqual(plan['tax_periods'][0]['tax_days'],16)
        self.assertEqual(plan['social_periods'][0]['days'],16)
        self.assertEqual(plan['gross_minor'],266667)
        self.assertEqual(plan['factor_parameters']['tax_factor'],'0.753')
        self.assertEqual(plan['factor_parameters']['profile_ref'],plan['selected_profile_ref'])
        self.assertEqual(plan['source_snapshot_hash'],periods.build_period_plan(snapshot)['source_snapshot_hash'])
        self.assertNotEqual(plan['plan_hash'],periods.build_period_plan(snapshot)['plan_hash'])
        result=calculate_factor_period_source(snapshot)
        self.assertEqual(result['scope'],FACTOR_PERIOD_SCOPE)
        self.assertEqual(result['period_details']['plan_hash'],plan['plan_hash'])
        self.assertEqual(result['period_details']['tax_calculation']['inputs']['gross_remainder_minor'],11)

    def test_full_month_matches_existing_factor_v8_without_changing_that_rule(self):
        snapshot=source(start='2026-03-01',end='2026-03-31')
        result=calculate_factor_period_source(snapshot)
        old=calculate(snapshot['profiles'][0]['profile'],snapshot['month'],500000,full_month_confirmed=True)
        for key in ('gross_minor','employee_contributions','employer_contributions','employer_levies',
                'individual_wage_tax_minor','solidarity_minor','church_tax_minor','net_minor'):
            self.assertEqual(result[key],old[key],key)
        self.assertNotEqual(result['rule_version'],old['rule_version'])

    def test_only_the_explicit_factor_blocker_is_resolved(self):
        snapshot=source();snapshot['profiles'][0]['profile']['special_cases']=['other_special_case','tax_factor']
        result=calculate_factor_period_source(snapshot)
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertEqual([x['code'] for x in result['blockers']],['special_case:other_special_case'])
        self.assertIsNone(result['net_minor'])
        self.assertTrue(any(x['code']=='special_case:tax_factor' for x in periods.build_period_plan(snapshot)['blockers']))

    def test_missing_identity_zero_gross_and_profile_change_stay_blocked(self):
        for mutate in (lambda s:s.update(identities=[]),
                lambda s:s['preparation']['snapshot']['agreements'][0].update(amount_minor=0),
                lambda s:s['profiles'].append({**deepcopy(s['profiles'][0]),'id':'9'*32,
                    'profile':dict(s['profiles'][0]['profile'],effective_from='2026-03-10')})):
            snapshot=source();mutate(snapshot)
            self.assertFalse(calculate_factor_period_source(snapshot)['payroll_calculation_complete'])

    def test_no_missing_factor_or_wrong_rule_can_be_guessed(self):
        with self.assertRaises(Problem):build_factor_period_plan(periods.period_snapshot())
        with self.assertRaises(Problem):calculate_factor_period_source(source(),rule_version='de_2026_periods_pap_v4')
        for lzz,days in ((True,30),(2,29),(4,0),(4,True),(3,7)):
            with self.subTest(lzz=lzz,days=days),self.assertRaises(Problem):
                calculate_factor_period_tax(gross_minor=10000,lzz=lzz,tax_days=days,factor='0.753',
                    tax_class=4,children_half_units=0,additional_health_percent='2.90',saxony=False,
                    childless_surcharge=True,care_child_discounts=0,church_member=False)

    def test_age_allowance_before_year_start_is_not_guessed_as_zero(self):
        result=calculate_factor_period_source(source(date_of_birth='1961-06-30'))
        self.assertFalse(result['payroll_calculation_complete'])
        self.assertIn('age_allowance_not_supported',[entry['code'] for entry in result['blockers']])
        self.assertIsNone(result['net_minor'])


if __name__=='__main__':unittest.main()
