"""Published annual BMF values plus separately derived MSONST edge cases."""
import json
from pathlib import Path
import unittest

from core import Problem
from payroll_pap_oneoff_2026 import calculate_standard_one_off_tax


class OneOffPapTests(unittest.TestCase):
    def calculate(self,**changes):
        args=dict(annual_pay_before_minor=9000000,one_off_minor=250000,
            tax_class=1,children_half_units=0,additional_health_percent='2.90',
            saxony=False,childless_surcharge=True,care_child_discounts=0,
            church_member=True,annual_allowance_minor=0,annual_addition_minor=0)
        args.update(changes)
        return calculate_standard_one_off_tax(**args)

    def test_252_cases_derived_from_independently_read_official_annual_table(self):
        source=Path(__file__).resolve().parents[1]/'docs/evidence/payroll-oneoff-2026-derived-pap-references.json'
        data=json.loads(source.read_text())
        cases=data['special_cases']
        self.assertEqual(len(cases),252)
        for case in cases:
            with self.subTest(JRE4=case['JRE4'],tax_class=case['tax_class']):
                result=self.calculate(annual_pay_before_minor=case['JRE4'],
                    one_off_minor=case['SONSTB'],tax_class=case['tax_class'],
                    childless_surcharge=case['tax_class']!=2)
                self.assertEqual({key:result[key] for key in ('STS','SOLZS','BKS')},case['expected'])

    def test_solidarity_is_not_the_difference_of_annual_solidarity(self):
        result=self.calculate()
        self.assertEqual((result['annual_tax_before_minor'],result['annual_tax_after_minor']),
                         (1943800,2039000))
        self.assertEqual((result['STS'],result['SOLZS'],result['BKS']),(95200,5236,95200))
        self.assertNotEqual(result['SOLZS'],476)

    def test_solidarity_half_cent_is_discarded(self):
        result=self.calculate(annual_pay_before_minor=9250000)
        self.assertEqual((result['STS'],result['SOLZS']),(95300,5241))

    def test_child_allowance_affects_solidarity_threshold_not_special_church_base(self):
        # JRE4+SONSTB=92500; annual precaution=ceil(8602.50+7567.87)=16171.
        # ZVE=75063; half child allowance=4878; tariff floor(.42*70185-11135.63)=18342.
        result=self.calculate(children_half_units=1)
        self.assertEqual(result['annual_solidarity_assessment_minor'],1834200)
        self.assertEqual((result['STS'],result['SOLZS'],result['BKS']),(95200,0,95200))

    def test_membership_does_not_change_solidarity_threshold(self):
        result=self.calculate(church_member=False)
        self.assertEqual((result['STS'],result['SOLZS'],result['BKS']),(95200,5236,0))
        child=self.calculate(church_member=False,children_half_units=1)
        self.assertEqual((child['STS'],child['SOLZS'],child['BKS']),(95200,0,0))

    def test_exact_annual_freigrenze_is_exempt_but_next_euro_is_not(self):
        # Gross 92393: precaution 16161; ZVE 74966 -> floor(20350.09)=20350.
        # Gross 92396: same precaution; ZVE 74969 -> floor(20351.35)=20351.
        exact=self.calculate(annual_pay_before_minor=8989300)
        above=self.calculate(annual_pay_before_minor=8989600)
        self.assertEqual((exact['annual_tax_after_minor'],exact['STS'],exact['SOLZS']),
                         (2035000,95300,0))
        self.assertEqual((above['annual_tax_after_minor'],above['STS'],above['SOLZS']),
                         (2035100,95300,5241))

    def test_zero_other_payment_does_not_repeat_the_running_tax(self):
        result=self.calculate(one_off_minor=0)
        self.assertEqual((result['STS'],result['SOLZS'],result['BKS']),(0,0,0))

    def test_input_amounts_and_standard_profile_preconditions_are_checked(self):
        for values in ({'one_off_minor':True},{'annual_pay_before_minor':-1},
                       {'one_off_minor':1.0},{'annual_pay_before_minor':10**12,'one_off_minor':1},
                       {'church_member':1},{'annual_allowance_minor':False},
                       {'additional_health_percent':'2.905'},
                       {'children_half_units':1,'tax_class':5},
                       {'care_child_discounts':1,'childless_surcharge':True}):
            with self.subTest(values=values),self.assertRaises(Problem):self.calculate(**values)
