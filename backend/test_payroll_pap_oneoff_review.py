"""Independent hand-derived MSONST values from PAP2026 pp33–37.

No tested annual primitive computes these expected values. The fixed examples
use the linear tariff zone with separately derived precaution deductions.
"""
import unittest

from payroll_pap_oneoff_2026 import calculate_standard_one_off_tax


def calculate(**changes):
    return calculate_standard_one_off_tax(**(dict(
        annual_pay_before_minor=15000000, one_off_minor=123456,
        tax_class=1, children_half_units=0, additional_health_percent='2.90',
        saxony=False, childless_surcharge=True, care_child_discounts=0,
        church_member=True, annual_allowance_minor=100055,
        annual_addition_minor=20049) | changes))


class IndependentOneOffPapReview(unittest.TestCase):
    def test_annual_allowance_and_addition_apply_to_both_comparisons_before_tariff(self):
        # Precaution ceil(9430.20 + 7567.87)=16999, fixed1266;
        # taxable annual130934.94/132169.50 -> tariff43856/44375 EUR.
        actual=calculate()
        self.assertEqual((4385600,4437500,51900,2854,51900),tuple(actual[key] for key in
            ('annual_tax_before_minor','annual_tax_after_minor','STS','SOLZS','BKS')))

    def test_one_cent_at_tariff_floor_boundary_does_not_silently_cap_tax_to_bonus(self):
        # ZVE131734.99/131735.00 -> tariff44192/44193 EUR.
        actual=calculate(annual_pay_before_minor=14999999,one_off_minor=1,
                         annual_allowance_minor=0,annual_addition_minor=0)
        self.assertEqual((4419200,4419300,100,5,100),tuple(actual[key] for key in
            ('annual_tax_before_minor','annual_tax_after_minor','STS','SOLZS','BKS')))

    def test_class_three_splits_before_euro_rounding_and_doubles_threshold(self):
        # Half taxable140467.47/141084.75; tariff47860/48119 each,
        # doubled annual95720/96238, so other-payment tax518EUR.
        actual=calculate(annual_pay_before_minor=30000000,tax_class=3)
        self.assertEqual((9572000,9623800,51800,2849,4070000),tuple(actual[key] for key in
            ('annual_tax_before_minor','annual_tax_after_minor','STS','SOLZS','solidarity_threshold_minor')))

    def test_crossing_annual_pension_cap_recomputes_precaution_before_tax_difference(self):
        # Before: ceil(9300+7567.87)=16868; after: ceil(9430.20+7567.87)=16999.
        # ZVE81866/83735 -> linear tariff23248/24033 EUR.
        actual=calculate(annual_pay_before_minor=10000000,one_off_minor=200000,
                         annual_allowance_minor=0,annual_addition_minor=0)
        self.assertEqual((2324800,2403300,78500,4317,78500),tuple(actual[key] for key in
            ('annual_tax_before_minor','annual_tax_after_minor','STS','SOLZS','BKS')))


if __name__=='__main__':
    unittest.main()
