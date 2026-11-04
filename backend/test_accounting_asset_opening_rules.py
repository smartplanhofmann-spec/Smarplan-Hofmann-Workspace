"""Independent dated and cent examples for the bounded old-asset contract."""
import unittest
from core import Problem
from accounting_asset_opening_rules import asset_key, normalize_asset, original_schedule, continuation


def asset(**changes):
    return dict(inventory_number='M-001',description='Synthetic previously acquired machine',asset_kind='movable',
                business_use='exclusive_business',method='linear',rounding='cumulative_months_half_up',
                acquired_on='2024-01-03',use_start='2024-01-03',life_months=36,
                acquisition_gross='4284.00',deductible_input_tax='684.00',cost_basis='3600.00',
                depreciation_before_start_year='2400.00',depreciation_in_start_year='0.00',
                opening_book_value='1200.00',account='0440',unchanged_linear_history_confirmed=True)|changes


class HistoricalLinearRuleExamples(unittest.TestCase):
    def test_cutover_does_not_reset_old_start_or_create_second_yearly_depreciation(self):
        value=asset(depreciation_in_start_year='500.00',opening_book_value='700.00')
        self.assertEqual(normalize_asset(value,'2026-07-17'),value)
        result=continuation(value,'2026-07-17',2026)
        self.assertEqual((result['original_annual_depreciation'],result['imported_current_year_depreciation'],result['amount']),('1200.00','500.00','700.00'))
        self.assertEqual(result['closing_book_value'],'0.00');self.assertEqual(value['use_start'],'2024-01-03')

    def test_documented_cent_roundings_are_kept_distinct_and_consume_exact_original_basis(self):
        cases={'cumulative_months_half_up':(['33.33','33.34','33.33'],'66.67','33.33'),
               'annual_half_up':(['33.33','33.33','33.34'],'66.66','33.34'),
               'monthly_half_up':(['33.36','33.36','33.28'],'66.72','33.28')}
        for method,(amounts,past,remaining) in cases.items():
            with self.subTest(method=method):
                value=asset(rounding=method,acquisition_gross='119.00',deductible_input_tax='19.00',cost_basis='100.00',
                            depreciation_before_start_year=past,opening_book_value=remaining)
                self.assertEqual([row['amount'] for row in original_schedule(value)],amounts)
                self.assertEqual(continuation(value,'2026-01-01',2026)['amount'],remaining)

    def test_fully_depreciated_still_used_asset_stays_zero_without_fictitious_rate(self):
        value=asset(acquired_on='2021-12-31',use_start='2021-12-31',depreciation_before_start_year='3600.00',opening_book_value='0.00')
        normalize_asset(value,'2026-01-01')
        result=continuation(value,'2026-01-01',2026)
        self.assertEqual((result['amount'],result['opening_book_value'],result['closing_book_value']),('0.00','0.00','0.00'))
        self.assertEqual(result['prior_required_years'],[])

    def test_leap_day_acquisition_uses_original_month_and_preserves_later_dependency(self):
        value=asset(acquired_on='2024-02-29',use_start='2024-02-29',life_months=48,
                    depreciation_before_start_year='1725.00',opening_book_value='1875.00')
        rows=original_schedule(value)
        self.assertEqual([(row['year'],row['months'],row['amount']) for row in rows],
                         [(2024,11,'825.00'),(2025,12,'900.00'),(2026,12,'900.00'),(2027,12,'900.00'),(2028,1,'75.00')])
        self.assertEqual(continuation(value,'2026-01-01',2028)['prior_required_years'],[2026,2027])

    def test_unknown_history_or_unsupported_method_is_not_a_zero_or_new_purchase(self):
        for changes in (dict(method='degressive'),dict(rounding='guess'),dict(business_use='mixed'),dict(asset_kind='building'),
                        dict(unchanged_linear_history_confirmed=False),dict(depreciation_in_start_year=None),
                        dict(depreciation_before_start_year='2399.00',opening_book_value='1201.00'),
                        dict(depreciation_in_start_year='1.00',opening_book_value='1199.00'),
                        dict(cost_basis='4284.00'),dict(use_start='2026-01-01'),dict(life_months=True)):
            with self.subTest(changes=changes),self.assertRaises(Problem):normalize_asset(asset(**changes),'2026-01-01')

    def test_inventory_identity_normalization_prevents_simple_duplicate_keys(self):
        self.assertEqual(asset_key(' M-001 '),asset_key('m-001'))
        self.assertEqual(asset_key('Ｍ-001'),asset_key('m-001'))


if __name__=='__main__':unittest.main()
