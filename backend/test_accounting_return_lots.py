"""Version separation and original-basis return cents, without database fixtures."""
from dataclasses import FrozenInstanceError
from fractions import Fraction
import unittest

from accounting_component_segments import CentAmounts
from accounting_return_lots import LotIdentity, RefundLineIdentity, ReturnedLot


ENTRY = 'a'*32
GROUP = 'b'*64
REFUND = 'c'*32


def exact_tax(gross, original_tax, original_gross):
    return int(Fraction(gross*original_tax, original_gross)+Fraction(1, 2))


class ReturnLotTests(unittest.TestCase):
    def test_equal_raw_ids_in_different_versions_remain_distinct(self):
        c1 = LotIdentity('c1', ENTRY, GROUP); c2 = LotIdentity('c2', ENTRY, GROUP)
        self.assertNotEqual(c1, c2); self.assertEqual(len({c1, c2}), 2)
        claims = {RefundLineIdentity('r1', REFUND, c1), RefundLineIdentity('r2', REFUND, c1),
                  RefundLineIdentity('r2', REFUND, c2)}
        self.assertEqual(len(claims), 3)
        self.assertEqual(RefundLineIdentity('r2', REFUND, c1), RefundLineIdentity('r2', REFUND, LotIdentity('c1', ENTRY, GROUP)))

    def test_every_identity_component_matters(self):
        original = RefundLineIdentity('r2', REFUND, LotIdentity('c1', ENTRY, GROUP))
        changed = (RefundLineIdentity('r1', REFUND, original.origin),
                   RefundLineIdentity('r2', 'd'*32, original.origin),
                   RefundLineIdentity('r2', REFUND, LotIdentity('c2', ENTRY, GROUP)),
                   RefundLineIdentity('r2', REFUND, LotIdentity('c1', 'd'*32, GROUP)),
                   RefundLineIdentity('r2', REFUND, LotIdentity('c1', ENTRY, 'd'*64)))
        self.assertEqual(len(set(changed) | {original}), 6)

    def test_old_refund_version_cannot_reference_new_positive_lots(self):
        with self.assertRaisesRegex(ValueError, 'only a c1 lot'):
            RefundLineIdentity('r1', REFUND, LotIdentity('c2', ENTRY, GROUP))

    def test_versions_and_identifiers_are_exact_and_never_normalized(self):
        for version in ('C1', 'c3', '', None, True, 1):
            with self.subTest(origin_version=version), self.assertRaises(ValueError):
                LotIdentity(version, ENTRY, GROUP)
        for version in ('R2', 'r3', '', None, True, 2):
            with self.subTest(refund_version=version), self.assertRaises(ValueError):
                RefundLineIdentity(version, REFUND, LotIdentity('c1', ENTRY, GROUP))
        for entry in ('A'*32, 'a'*31, 'a'*33, 'a'*31+'g', ' '+ENTRY, ENTRY+'\n', None, 1):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                LotIdentity('c1', entry, GROUP)
            with self.subTest(refund_entry=entry), self.assertRaises(ValueError):
                RefundLineIdentity('r2', entry, LotIdentity('c1', ENTRY, GROUP))
        for group in ('B'*64, 'b'*63, 'b'*65, 'g'*64, None, False):
            with self.subTest(group=group), self.assertRaises(ValueError):
                LotIdentity('c2', ENTRY, group)
        with self.assertRaises(ValueError):
            RefundLineIdentity('r2', REFUND, ('c1', ENTRY, GROUP))

    def test_middle_lot_partial_r1_then_r2_keeps_original_tax_counter(self):
        basis = CentAmounts(3333, 634, 3967)
        # These are the already established R1 cents of the original middle lot.
        prior = CentAmounts(1111, 211, 1322)
        state = ReturnedLot(basis, prior)
        returned, second = state.return_cents(1322)
        self.assertEqual(returned, CentAmounts(1110, 212, 1322))
        final, exhausted = second.return_cents(1323)
        self.assertEqual(final, CentAmounts(1112, 211, 1323))
        self.assertEqual(exhausted.previously_returned, basis)
        self.assertEqual(exhausted.remaining_amounts, CentAmounts(0, 0, 0))
        self.assertIs(second.basis, basis); self.assertIs(exhausted.basis, basis)
        # Rebaselining the remaining cents would incorrectly allocate 211 tax.
        self.assertEqual(exact_tax(1322, state.remaining_amounts.tax, state.remaining_amounts.gross), 211)
        self.assertEqual(returned.tax, 212)

    def test_same_gross_group_lots_keep_their_different_frozen_tax_cents(self):
        first = ReturnedLot(CentAmounts(3334, 633, 3967), CentAmounts(1111, 211, 1322))
        middle = ReturnedLot(CentAmounts(3333, 634, 3967), CentAmounts(1111, 211, 1322))
        first_return, unused = first.return_cents(1322)
        middle_return, unused = middle.return_cents(1322)
        self.assertEqual((first_return.tax, middle_return.tax), (211, 212))

    def test_self_consistent_but_wrong_prior_net_tax_split_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original cumulative'):
            ReturnedLot(CentAmounts(3333, 634, 3967), CentAmounts(1110, 212, 1322))
        with self.assertRaisesRegex(ValueError, 'original cumulative'):
            ReturnedLot(CentAmounts(1, 1, 2), CentAmounts(1, 0, 1))

    def test_all_small_prior_counters_and_positive_deltas_match_exact_fraction_oracle(self):
        checked = 0
        for original_gross in range(1, 13):
            for original_tax in range(original_gross+1):
                basis = CentAmounts(original_gross-original_tax, original_tax, original_gross)
                for prior_gross in range(original_gross):
                    prior_tax = exact_tax(prior_gross, original_tax, original_gross)
                    prior = CentAmounts(prior_gross-prior_tax, prior_tax, prior_gross)
                    state = ReturnedLot(basis, prior)
                    for amount in range(1, original_gross-prior_gross+1):
                        with self.subTest(basis=basis, prior=prior, amount=amount):
                            returned, following = state.return_cents(amount)
                            after_tax = exact_tax(prior_gross+amount, original_tax, original_gross)
                            self.assertEqual(returned, CentAmounts(amount-after_tax+prior_tax, after_tax-prior_tax, amount))
                            self.assertEqual(following.previously_returned, CentAmounts(prior_gross+amount-after_tax, after_tax, prior_gross+amount))
                            self.assertEqual(state.previously_returned, prior)
                            self.assertEqual(following.remaining_amounts.gross+following.previously_returned.gross, original_gross)
                        checked += 1
        self.assertEqual(checked, 3731)

    def test_exact_half_cent_rounds_up_and_final_return_exhausts_the_basis(self):
        state = ReturnedLot(CentAmounts(1, 1, 2))
        first, state = state.return_cents(1)
        last, state = state.return_cents(1)
        self.assertEqual(first, CentAmounts(0, 1, 1)); self.assertEqual(last, CentAmounts(1, 0, 1))
        self.assertEqual(state.remaining_amounts, CentAmounts(0, 0, 0))

    def test_arbitrary_integer_precision_has_no_float_rounding_or_counter_reset(self):
        gross = 10**60+7; tax = 10**59+3; prior_gross = gross//3
        prior_tax = exact_tax(prior_gross, tax, gross)
        state = ReturnedLot(CentAmounts(gross-tax, tax, gross), CentAmounts(prior_gross-prior_tax, prior_tax, prior_gross))
        returned, following = state.return_cents(gross-prior_gross)
        self.assertEqual(returned.tax, tax-prior_tax)
        self.assertEqual(following.previously_returned, state.basis)

    def test_invalid_amounts_overreturn_and_zero_original_lots_are_rejected(self):
        state = ReturnedLot(CentAmounts(3, 1, 4), CentAmounts(1, 1, 2))
        for value in (True, False, 0, -1, 1.0, '1', None, 3):
            with self.subTest(amount=value), self.assertRaises(ValueError):
                state.return_cents(value)
        with self.assertRaises(ValueError):
            ReturnedLot(CentAmounts(0, 0, 0))
        with self.assertRaises(ValueError):
            ReturnedLot(CentAmounts(3, 1, 4), CentAmounts(4, 1, 5))
        with self.assertRaises(ValueError):
            ReturnedLot((3, 1, 4))
        with self.assertRaises(ValueError):
            ReturnedLot(CentAmounts(3, 1, 4), (0, 0, 0))

    def test_state_and_versioned_identities_are_frozen_and_inputs_are_preserved(self):
        identity = LotIdentity('c1', ENTRY, GROUP)
        claim = RefundLineIdentity('r2', REFUND, identity)
        state = ReturnedLot(CentAmounts(3333, 634, 3967))
        prior = state.previously_returned
        unused, following = state.return_cents(1322)
        self.assertEqual(state.previously_returned, prior); self.assertIs(following.basis, state.basis)
        for target, name, value in ((identity, 'origin_version', 'c2'), (claim, 'refund_version', 'r1'),
                                    (state, 'previously_returned', following.previously_returned)):
            with self.subTest(target=target), self.assertRaises(FrozenInstanceError):
                setattr(target, name, value)


if __name__ == '__main__':
    unittest.main()
