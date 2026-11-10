"""Original-source partial factor/Midijob cases against independent XML/Fraction values."""
from copy import deepcopy
import calendar
import json
from pathlib import Path
import unittest

from core import Problem
from payroll_factor_periods_2026 import build_factor_period_plan, calculate_factor_period_source
from payroll_factor_transition_periods_2026 import (
    build_plan, calculate_source, normalize_case_assessment, RULE_VERSION, SCOPE, FINANCIAL_FIELDS,
)
from test_payroll_periods_2026 import period_snapshot
from test_payroll_transition_2026 import assessment


def snapshot(amount=100000, *, start='2026-10-15', end='2026-10-31', method='contractual_30_days', month='2026-10', **profile):
    parameters = dict(tax_class=4, special_cases=['tax_factor'], tax_factor='0.753') | profile
    original = period_snapshot(month=month, start=start, end=end, amount=amount, method=method, **parameters)
    original['identities'][0]['details'].update(tax_source='elstam_imported',
        tax_allowance_yearly_minor=0, tax_addition_yearly_minor=0)
    employee = original['employee_id']
    evidence = dict(id='0'*32, revision=1, content_hash='0'*64)
    review = dict(schema_version=1, employee_id=employee, valid_from=month+'-01', valid_to=month+f'-{calendar.monthrange(2026,int(month[5:]))[1]:02}',
        declaration_date=month+'-01', transition_assessment=assessment(amount), forecast_evidence_ref=evidence,
        sole_employment_confirmed=True, fixed_monthly_contract_confirmed=True, contractual_30_days_confirmed=True,
        verification_note='Synthetic original fixed contract and independent actual status prognosis')
    base = dict(id='1'*32, revision=1, content_hash='1'*64, kind='period_case', status='active',
        employee_id=employee, details=deepcopy(original['case_details']), sources=original,
        plan=build_factor_period_plan(original))
    return dict(schema_version=1, source_contract_version=7, rule_version=RULE_VERSION,
        employee_id=employee, month=month, period_case=base,
        employment_terms=[deepcopy(original['employment_terms'])], profiles=deepcopy(original['profiles']),
        identities=deepcopy(original['identities']), segment_events=[], thirty_day_rule='actual_days_capped_per_claim',
        entitlements=[], travel_sources=[], flat_travel_tax=None,
        source_files=[dict(evidence, employee_id=employee, purpose='personnel')],
        factor_transition_period_assessment=review)


class FactorTransitionPeriods(unittest.TestCase):
    def test_three_hundred_independent_xml_and_exact_rational_contribution_vectors(self):
        proof = json.loads(Path(__file__).with_name('testdata').joinpath('payroll_factor_transition_periods_2026.json').read_text())
        self.assertFalse(proof['production_kernel_imported'])
        self.assertEqual(proof['xml_sha256'], '63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4')
        self.assertEqual(len(proof['cases']), 300)
        for row in proof['cases']:
            p, expected = row['input'], row['expected']
            original = snapshot(p['monthly_minor'], start=f"2026-10-{32-p['days']:02}",
                tax_factor=p['factor'], tax_children_half_units=p['children_half_units'],
                federal_state=p['federal_state'], church_tax='standard' if p['church_member'] else 'none',
                has_children=not p['childless_surcharge'],
                pv_children_under_25=p['care_child_discounts']+1 if not p['childless_surcharge'] else 0)
            with self.subTest(input=p):
                actual = calculate_source(original)
                self.assertTrue(actual['payroll_calculation_complete'])
                self.assertEqual(actual['scope'], SCOPE)
                self.assertEqual(actual['gross_minor'], p['gross_minor'])
                self.assertEqual(actual['individual_wage_tax_minor'], expected['tax']['LSTLZZ'])
                self.assertEqual(actual['solidarity_minor'], expected['tax']['SOLZLZZ'])
                self.assertEqual(actual['tax_parameters']['church_assessment_minor'], expected['tax']['BK'])
                self.assertEqual(actual['church_tax_minor'], expected['church_tax_minor'])
                self.assertEqual(actual['net_minor'], expected['net_minor'])
                for key in ('employee_contributions', 'employer_contributions', 'employer_levies'):
                    self.assertEqual(actual[key], expected['social'][key])
                for key in ('total_assessment_minor', 'employee_assessment_minor'):
                    self.assertEqual(actual['transition'][key], expected['social'][key])

    def test_actual_exit_february_and_thirty_first_preserve_original_calendar_and_sv_days(self):
        for month, start, end, days, gross in [
            ('2026-10', '2026-01-01', '2026-10-16', 16, 53333),
            ('2026-02', '2026-02-15', '2026-02-28', 14, 46667),
            ('2026-07', '2026-07-31', '2026-07-31', 1, 3333),
            ('2026-10', '2026-10-02', '2026-10-31', 30, 100000),
        ]:
            with self.subTest(month=month, start=start, end=end):
                source = snapshot(month=month, start=start, end=end)
                before = deepcopy(source)
                result = calculate_source(source)
                self.assertTrue(result['payroll_calculation_complete'], result['blockers'])
                self.assertEqual(result['gross_minor'], gross)
                self.assertEqual(result['period_details']['social_periods'][0]['days'], days)
                self.assertEqual(result['period_details']['tax_periods'][0]['tax_days'], days)
                self.assertEqual(result['period_details']['tax_periods'][0]['lzz'], 4)
                self.assertEqual(source, before)
        full = calculate_source(snapshot(month='2026-02', start='2026-02-01', end='2026-02-28'))
        self.assertFalse(full['payroll_calculation_complete'])
        self.assertTrue(all(full[k] is None for k in FINANCIAL_FIELDS))

    def test_original_profile_period_rule_and_full_snapshot_remain_unchanged(self):
        s = snapshot(); before = deepcopy(s)
        old = calculate_factor_period_source(s['period_case']['sources'])
        self.assertFalse(old['payroll_calculation_complete'])
        self.assertIn('transition_assessment_missing', [r['code'] for r in old['blockers']])
        actual = calculate_source(s)
        self.assertTrue(actual['payroll_calculation_complete'])
        self.assertEqual(s, before)
        self.assertNotIn('transition_assessment', s['profiles'][0]['profile'])
        self.assertEqual(calculate_factor_period_source(s['period_case']['sources']), old)
        self.assertEqual(actual['period_details']['social_periods'][0]['days'], 17)
        self.assertEqual(actual['period_details']['tax_periods'][0]['tax_days'], 17)
        self.assertEqual(actual['gross_minor'], 56667)
        self.assertNotEqual(build_plan(s)['plan_hash'], s['period_case']['plan']['plan_hash'])
        self.assertFalse(actual['official_system_approval'])
        self.assertEqual(actual['statutory_report_status'], 'not_transmitted')

    def test_other_contracts_full_month_and_unchecked_reviews_never_produce_money(self):
        variants = [snapshot(start='2026-10-01'), snapshot(method='calendar_days_actual'),
            snapshot(health_insurance='private'), snapshot(special_cases=['tax_factor', 'one_off_payment'])]
        for name in ('sole_employment_confirmed', 'fixed_monthly_contract_confirmed', 'contractual_30_days_confirmed'):
            s = snapshot(); s['factor_transition_period_assessment'][name] = False; variants.append(s)
        s = snapshot(); s['factor_transition_period_assessment']['valid_from'] = '2026-10-16'; variants.append(s)
        s = snapshot(); s['factor_transition_period_assessment']['transition_assessment']['assessed_on'] = '2026-10-16'; variants.append(s)
        for s in variants:
            with self.subTest(review=s['factor_transition_period_assessment'], method=s['employment_terms'][0]['details']['proration_method']):
                actual = calculate_source(s)
                self.assertFalse(actual['payroll_calculation_complete'])
                self.assertFalse(actual['social_contributions_available'])
                self.assertEqual(actual['scope'], 'unsupported')
                self.assertTrue(actual['blockers'])
                self.assertEqual(actual['period_details']['social_assessments'], [])
                self.assertTrue(all(actual[k] is None for k in FINANCIAL_FIELDS))

    def test_fresh_reference_binding_and_explicit_version_shapes_are_mandatory(self):
        variants = []
        s = snapshot(); s['period_case']['plan']['gross_minor'] += 1; variants.append(s)
        s = snapshot(); s['source_files'][0]['content_hash'] = 'f'*64; variants.append(s)
        s = snapshot(); s['source_files'][0]['employee_id'] = 'a'*32; variants.append(s)
        s = snapshot(); s['source_contract_version'] = True; variants.append(s)
        s = snapshot(); s['source_contract_version'] = 6; variants.append(s)
        s = snapshot(); s['thirty_day_rule'] = None; variants.append(s)
        s = snapshot(); s['factor_transition_period_assessment']['employee_id'] = 'b'*32; variants.append(s)
        s = snapshot(); s['profiles'][0]['profile']['verification_note'] = 'Changed original'; variants.append(s)
        for s in variants:
            with self.subTest(input=s), self.assertRaises(Problem):
                calculate_source(s)

    def test_review_rejects_bool_integers_foreign_fields_unpaired_text_and_old_full_month_shape(self):
        review = snapshot()['factor_transition_period_assessment']
        invalid = [dict(review, schema_version=True), dict(review, unknown=True),
            dict(review, contractual_30_days_confirmed=1), dict(review, verification_note='\ud800'),
            dict(review, forecast_evidence_ref=review['forecast_evidence_ref'] | dict(revision=True)),
            dict(review, transition_assessment=assessment(100000, forecast_months=11))]
        for item in invalid:
            with self.subTest(input=item), self.assertRaises(Problem):
                normalize_case_assessment(item)
        self.assertEqual(normalize_case_assessment(review), review)


if __name__ == '__main__':
    unittest.main()
