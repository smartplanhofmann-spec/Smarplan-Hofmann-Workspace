"""Independent v5 boundary and money-conservation review, before rule freeze."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import unittest

from core import Problem, canonical
from payroll_calculations_2026 import (build_calculation_plan,
    calculate_calculation_source, CALCULATION_RULE_VERSION)
from test_payroll_calculations_2026 import source, travel, flat_policy
from test_payroll_claims_composition_2026 import fact
from test_payroll_entitlements_2026 import unpaid


def result(value):
    return calculate_calculation_source(value, rule_version=CALCULATION_RULE_VERSION,
                                        source_contract_version=1)


def product(cents, percent):
    return int((Decimal(cents)*Decimal(percent)/100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


class CompositeIndependentReview(unittest.TestCase):
    def test_partial_month_actual_day_caps_apply_to_each_branch_separately(self):
        value = source(month='2026-07', start='2026-07-16', amount=620000)
        actual = result(value)
        self.assertTrue(actual['payroll_calculation_complete'], actual['blockers'])
        detail = actual['period_details']
        # 16 actual days; the actual-days wage contract divides by July's31.
        self.assertEqual(320000, actual['gross_minor'])
        self.assertEqual((4,16), (detail['tax_periods'][0]['lzz'], detail['tax_periods'][0]['tax_days']))
        period = detail['social_periods'][0]
        self.assertEqual(16, period['days'])
        self.assertEqual((310000,450667), (period['caps']['health_minor'], period['caps']['pension_minor']))
        profile = value['profiles'][0]['profile']
        expected = dict(health_general=product(310000,'7.3'),
            health_additional=product(310000,str(Decimal(profile['health_additional_percent'])/2)),
            pension=product(320000,'9.3'), unemployment=product(320000,'1.3'),
            care=product(310000,'2.4'))
        self.assertEqual(expected, actual['employee_contributions'])
        self.assertEqual(actual['gross_minor']-sum(expected.values())-actual['employee_tax_minor'], actual['payout_minor'])

    def test_tax_free_external_reimbursement_never_reappears_in_payroll_cash_or_cost(self):
        base = result(source(amount=420000))
        value = source(amount=420000)
        travel(value, m=True)
        adapter = value['travel_sources'][0]
        adapter['tax_free_external_minor'] = 98000
        adapter['source_hash'] = hashlib.sha256(canonical({k:v for k,v in adapter.items() if k!='source_hash'}).encode()).hexdigest()
        actual = result(value)
        for name in ('gross_minor','net_minor','payout_minor','employee_social_total_minor',
                     'employee_tax_minor','employer_total_excluding_accident_insurance_minor'):
            self.assertEqual(base[name],actual[name], name)
        self.assertTrue(actual['period_details']['travel']['letter_m'])

    def test_cash_benefit_and_transferred_flat_tax_conserve_every_cent(self):
        value = source(amount=410000)
        travel(value, individual=1503, flat=1403, benefit=417, m=True)
        flat_policy(value,shift=True)
        actual = result(value)
        self.assertTrue(actual['payroll_calculation_complete'], actual['blockers'])
        self.assertEqual(413323, actual['gross_minor'])
        self.assertEqual(411920, actual['period_details']['tax_periods'][0]['gross_minor'])
        self.assertEqual(411920, actual['period_details']['social_periods'][0]['gross_minor'])
        self.assertEqual(384, actual['employer_flat_tax_minor'])
        self.assertEqual(801, actual['net_deductions_minor'])
        self.assertEqual(actual['gross_minor'], actual['payout_minor']+
            actual['employee_social_total_minor']+actual['employee_tax_minor']+801)
        self.assertEqual(actual['gross_minor']+actual['employer_social_total_minor']+
            sum(actual['employer_levies'].values()), actual['employer_total_excluding_accident_insurance_minor'])

    def test_foreign_travel_with_recomputed_adapter_hash_is_rejected(self):
        value = source(); travel(value, individual=1400)
        adapter = value['travel_sources'][0]
        self.assertNotEqual('f'*32, value['employee_id'])
        adapter['employee_id'] = 'f'*32
        adapter['source_hash'] = hashlib.sha256(canonical({k:v for k,v in adapter.items() if k!='source_hash'}).encode()).hexdigest()
        with self.assertRaises(Problem): result(value)

    def test_two_different_settlements_cannot_reuse_one_allocation_key(self):
        value = source(); travel(value, individual=1400)
        other = deepcopy(value['travel_sources'][0])
        other['settlement_ref'] = dict(id='6'*32, revision=1, content_hash='6'*64)
        other['source_hash'] = hashlib.sha256(canonical({k:v for k,v in other.items() if k!='source_hash'}).encode()).hexdigest()
        value['travel_sources'].append(other)
        with self.assertRaises(Problem): result(value)

    def test_arbitrary_stored_flat_tax_amount_cannot_enter_total_net(self):
        value = source(); travel(value,flat=1400); flat_policy(value)
        value['flat_travel_tax']['calculation']['statutory_employer_due_minor'] = 0
        with self.assertRaises(Problem): result(value)

    def test_no_insured_days_does_not_create_minimum_days_or_shorten_tax_lzz(self):
        value = source(amount=300000)
        value['entitlements'] = [fact('unpaid_continuation',
            unpaid('2026-09-01','2026-12-31'),value['employment_terms'][0])]
        actual = result(value)
        self.assertTrue(actual['payroll_calculation_complete'],actual['blockers'])
        self.assertEqual([],actual['period_details']['social_periods'])
        self.assertEqual((0,0,0,0),(actual['gross_minor'],actual['employee_social_total_minor'],
                                  actual['employee_tax_minor'],actual['payout_minor']))
        self.assertEqual((2,30),(actual['period_details']['tax_periods'][0]['lzz'],
                                actual['period_details']['tax_periods'][0]['tax_days']))

    def test_boolean_or_float_source_versions_do_not_alias_integer_version_one(self):
        for field in ('schema_version','source_contract_version'):
            for bad in (True,1.0):
                value=source();value[field]=bad
                with self.subTest(field=field,bad=bad),self.assertRaises(Problem):
                    build_calculation_plan(value,rule_version=CALCULATION_RULE_VERSION,source_contract_version=1)


if __name__=='__main__':
    unittest.main()
