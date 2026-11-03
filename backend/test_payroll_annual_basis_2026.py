"""Annual tax-period assignment boundaries from LStR39b.2 and39b.5."""
import unittest
from core import Problem
from payroll_annual_basis_2026 import running_tax_year


class AnnualTaxYearBoundaries(unittest.TestCase):
    def test_running_prior_year_wage_through_january_21_stays_in_original_tax_year(self):
        self.assertEqual(running_tax_year('2025-12-31','2026-01-21'),2025)
        self.assertEqual(running_tax_year('2026-10-31','2026-11-03'),2026)

    def test_later_prior_year_arrears_are_not_guessed_as_social_one_off_pay(self):
        for received in ('2026-01-22','2026-02-01'):
            with self.subTest(received=received),self.assertRaises(Problem):running_tax_year('2025-12-31',received)


if __name__=='__main__':unittest.main()
