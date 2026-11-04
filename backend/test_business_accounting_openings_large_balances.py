"""Real recorded movements may make a derived balance exceed input bounds."""
import unittest
from core import Problem
import test_business_accounting_openings as fixtures


class LargeDerivedOpeningBalances(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.OpeningWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_maximum_opening_plus_real_cash_preserves_exact_larger_derived_balance(self):
        f=self.f;income=f.fixture.sale();f.fixture.post('cash',f.fixture.cash_payload(income))
        f.save(amount='99999999999.99')
        view=f.api.liquidity(f.owner,'2026-11-02');row=view['accounts'][0]
        self.assertEqual(row['inflows'],'119.00');self.assertEqual(row['balance'],'100000000118.99')
        self.assertEqual(view['known_balance_sum'],'100000000118.99');self.assertEqual(view['balance_total'],'100000000118.99')
        with self.assertRaises(Problem) as caught:f.api.preview(f.owner,f.body(amount='100000000000.00'))
        self.assertEqual(caught.exception.status,400)

    def test_minimum_bank_opening_minus_real_cash_preserves_exact_larger_negative_balance(self):
        f=self.f;receipt=f.fixture.incoming();f.fixture.post('input_vat',f.fixture.vat_payload(receipt))
        expense=f.fixture.payout(receipt);f.fixture.post('cash',f.fixture.cash_payload(expense,'materials'))
        f.save(amount='-99999999999.99')
        view=f.api.liquidity(f.owner,'2026-11-02');row=view['accounts'][0]
        self.assertEqual(row['outflows'],'59.50');self.assertEqual(row['balance'],'-100000000059.49')
        self.assertEqual(view['known_balance_sum'],'-100000000059.49');self.assertEqual(view['balance_total'],'-100000000059.49')
        with self.assertRaises(Problem) as caught:f.api.preview(f.owner,f.body(amount='-100000000000.00'))
        self.assertEqual(caught.exception.status,400)


if __name__=='__main__':unittest.main()
