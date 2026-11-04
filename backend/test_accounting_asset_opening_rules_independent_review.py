"""Independent dated rational-cent oracle; no runtime mutation or old-journal rewrite.

Ordinary unchanged linear movable assets only. Historical rounding conventions
are explicit accounting evidence, not a recommendation of a new tax method.
"""
from collections import Counter
from datetime import date
from fractions import Fraction
import unittest

from core import Problem
from accounting_asset_opening_rules import (
    ROUNDING, normalize_asset, original_schedule, continuation,
)


def euro(cents):
    return f'{cents // 100}.{cents % 100:02d}'


def exact_half_up(value):
    quotient, remainder = divmod(value.numerator, value.denominator)
    return quotient + (2 * remainder >= value.denominator)


def rational_calendar_oracle(basis, life, acquired, rounding):
    """Enumerate actual calendar months, then round independent rational quotas."""
    start = date.fromisoformat(acquired)
    calendar = Counter((start.year * 12 + start.month - 1 + month) // 12
                       for month in range(life))
    results = []
    consumed = 0
    running_months = 0
    unit = Fraction(basis, life)
    for year, months in sorted(calendar.items()):
        if rounding == 'cumulative_months_half_up':
            amount = exact_half_up(unit * (running_months + months)) - exact_half_up(unit * running_months)
        elif rounding == 'annual_half_up':
            amount = exact_half_up(unit * months)
        elif rounding == 'monthly_half_up':
            amount = exact_half_up(unit) * months
        else:
            raise AssertionError('Oracle must never infer an unknown convention')
        if year == max(calendar):
            amount = basis - consumed
        amount = min(amount, basis - consumed)
        results.append(dict(year=year, months=months, amount=euro(amount),
                            opening_book_value=euro(basis - consumed),
                            closing_book_value=euro(basis - consumed - amount)))
        consumed += amount
        running_months += months
    return results


def documented(*, basis=360000, life=36, acquired='2024-01-03',
               rounding='cumulative_months_half_up', cutover='2026-01-01', already=0, **changes):
    rows = rational_calendar_oracle(basis, life, acquired, rounding)
    past = sum(int(row['amount'].replace('.', '')) for row in rows if row['year'] < int(cutover[:4]))
    return dict(inventory_number='INDEPENDENT-001', description='Independent synthetic ordinary linear machine',
                asset_kind='movable', business_use='exclusive_business', method='linear', rounding=rounding,
                acquired_on=acquired, use_start=acquired, life_months=life,
                acquisition_gross=euro(basis), deductible_input_tax='0.00', cost_basis=euro(basis),
                depreciation_before_start_year=euro(past), depreciation_in_start_year=euro(already),
                opening_book_value=euro(basis - past - already), account='0440',
                unchanged_linear_history_confirmed=True) | changes


class IndependentHistoricalAssetRulesReview(unittest.TestCase):
    def test_acquisition_month_cannot_be_shifted_six_months_by_later_use(self):
        # Source review found that the earlier implementation allowed this evidence and deferred
        # both the first-year allowance and terminal life by six months. The
        # narrow reviewed class now rejects the unmodelled start difference.
        value = documented(use_start='2024-07-03',
                           depreciation_before_start_year='1800.00', opening_book_value='1800.00')
        with self.assertRaises(Problem) as caught:
            normalize_asset(value, '2026-01-01')
        self.assertEqual(caught.exception.status, 409)

    def test_day_within_acquisition_month_does_not_change_twelfths(self):
        for acquired, used in [('2024-01-01', '2024-01-31'), ('2024-02-01', '2024-02-29'),
                              ('2024-12-01', '2024-12-31')]:
            with self.subTest(acquired=acquired):
                value = documented(acquired=acquired, use_start=used)
                normalize_asset(value, '2026-01-01')
                self.assertEqual(original_schedule(value), rational_calendar_oracle(360000, 36, acquired, value['rounding']))

    def test_original_schedules_match_rational_month_oracle_for_900_boundary_cases(self):
        count = 0
        for acquired in ['2024-01-01', '2024-01-31', '2023-02-28', '2024-02-29', '2024-12-31']:
            for life in [12, 24, 36, 48, 84, 1200]:
                for basis in [1, 2, 5, 99, 100, 101, 9999, 10000, 10001, 9999999999999]:
                    for rounding in ROUNDING:
                        with self.subTest(acquired=acquired, life=life, basis=basis, rounding=rounding):
                            value = documented(basis=basis, life=life, acquired=acquired, rounding=rounding)
                            expected = rational_calendar_oracle(basis, life, acquired, rounding)
                            actual = original_schedule(value)
                            self.assertEqual(actual, expected)
                            self.assertEqual(sum(row['months'] for row in actual), life)
                            self.assertEqual(sum(int(row['amount'].replace('.', '')) for row in actual), basis)
                            self.assertEqual(actual[-1]['closing_book_value'], '0.00')
                            normalize_asset(value, '2026-01-01')
                            carry = continuation(value, '2026-01-01', 2026)
                            expected_rate = next((row['amount'] for row in expected if row['year'] == 2026), '0.00')
                            self.assertEqual(carry['amount'], expected_rate)
                            self.assertEqual(carry['opening_book_value'], value['opening_book_value'])
                            self.assertEqual(carry['prior_required_years'], [])
                            count += 1
        self.assertEqual(count, 900)

    def test_original_cent_conventions_have_distinct_last_year_residuals(self):
        expected = {
            'cumulative_months_half_up': ['33.33', '33.34', '33.33'],
            'annual_half_up': ['33.33', '33.33', '33.34'],
            'monthly_half_up': ['33.36', '33.36', '33.28'],
        }
        for rounding, amounts in expected.items():
            with self.subTest(rounding=rounding):
                value = documented(basis=10000, rounding=rounding)
                normalize_asset(value, '2026-01-01')
                self.assertEqual([row['amount'] for row in original_schedule(value)], amounts)
                self.assertEqual(continuation(value, '2026-01-01', 2026)['amount'], amounts[-1])
                wrong = dict(value, depreciation_before_start_year='66.67', opening_book_value='33.33')
                if rounding != 'cumulative_months_half_up':
                    with self.assertRaises(Problem): normalize_asset(wrong, '2026-01-01')

    def test_same_year_acquisition_and_cutover_retain_original_month_and_subtract_only_evidenced_current_amount(self):
        for day in ['2026-03-01', '2026-03-31']:
            value = documented(acquired=day, cutover='2026-07-17', already=10000)
            normalize_asset(value, '2026-07-17')
            row = continuation(value, '2026-07-17', 2026)
            self.assertEqual((row['months'], row['original_annual_depreciation'], row['amount']), (10, '1000.00', '900.00'))
            self.assertEqual((row['opening_book_value'], row['closing_book_value']), ('3500.00', '2600.00'))
            self.assertEqual(continuation(value, '2026-07-17', 2029)['amount'], '200.00')

    def test_leap_year_and_december_acquisition_leave_exact_original_last_months(self):
        cases = [('2024-02-29', [(2024, 11, '1100.00'), (2025, 12, '1200.00'), (2026, 12, '1200.00'), (2027, 1, '100.00')]),
                 ('2024-12-31', [(2024, 1, '100.00'), (2025, 12, '1200.00'), (2026, 12, '1200.00'), (2027, 11, '1100.00')])]
        for acquired, expected in cases:
            value = documented(acquired=acquired)
            self.assertEqual([(row['year'], row['months'], row['amount']) for row in original_schedule(value)], expected)
            self.assertEqual(continuation(value, '2026-01-01', 2027)['prior_required_years'], [2026])

    def test_january_boundary_and_current_year_quota_cannot_create_double_depreciation(self):
        value = documented(cutover='2026-07-01', already=120000)
        normalize_asset(value, '2026-07-01')
        self.assertEqual(continuation(value, '2026-07-01', 2026)['amount'], '0.00')
        with self.assertRaises(Problem): normalize_asset(value, '2026-01-01')
        excess = documented(life=48, cutover='2026-07-01', already=90001)
        with self.assertRaises(Problem): normalize_asset(excess, '2026-07-01')
        missing = documented(depreciation_in_start_year=None)
        with self.assertRaises(Problem): normalize_asset(missing, '2026-07-01')

    def test_zero_rounded_years_and_fully_consumed_asset_do_not_require_fictitious_postings(self):
        tiny = documented(basis=1, life=1200, acquired='2024-01-01', rounding='monthly_half_up')
        normalize_asset(tiny, '2026-01-01')
        self.assertEqual(continuation(tiny, '2026-01-01', 2026)['amount'], '0.00')
        final = continuation(tiny, '2026-01-01', 2123)
        self.assertEqual((final['amount'], final['closing_book_value'], final['prior_required_years']), ('0.01', '0.00', []))
        exhausted = documented(acquired='2020-12-31')
        normalize_asset(exhausted, '2026-01-01')
        self.assertEqual(continuation(exhausted, '2026-01-01', 2026)['amount'], '0.00')
        self.assertEqual(continuation(exhausted, '2026-01-01', 2026)['prior_required_years'], [])

    def test_tax_basis_and_supported_class_require_explicit_matching_evidence(self):
        value = documented(acquisition_gross='4284.00', deductible_input_tax='684.00')
        normalize_asset(value, '2026-01-01')
        for change in [dict(cost_basis='4284.00'), dict(deductible_input_tax='4284.01'), dict(method='degressive'),
                       dict(method='gwg'), dict(asset_kind='building'), dict(business_use='mixed'),
                       dict(rounding='annual_half_even'), dict(life_months=True), dict(life_months=13),
                       dict(unchanged_linear_history_confirmed=False)]:
            with self.subTest(change=change), self.assertRaises(Problem):
                normalize_asset(value | change, '2026-01-01')


if __name__ == '__main__':
    unittest.main()
