"""Independent cent-conservation cases for the unconnected segment calculator."""
from dataclasses import FrozenInstanceError
from decimal import Decimal, ROUND_HALF_UP, localcontext
import unittest

from accounting_component_segments import CentAmounts, ComponentSegment


def cents(net, tax, gross):
    return CentAmounts(net=net, tax=tax, gross=gross)


class ComponentSegmentTests(unittest.TestCase):
    def original_two_lots(self):
        initial = ComponentSegment(cents(10000, 1900, 11900))
        first, second_state = initial.consume(3967)
        second, remaining_state = second_state.consume(3967)
        self.assertEqual(first, cents(3334, 633, 3967))
        self.assertEqual(second, cents(3333, 634, 3967))
        self.assertEqual(remaining_state.remaining_amounts, cents(3333, 633, 3966))
        return initial, first, second, remaining_state

    def test_original_three_lots_preserve_the_different_rounding_cents(self):
        original, first, second, state = self.original_two_lots()
        last, exhausted = state.consume(3966)
        self.assertEqual(last, cents(3333, 633, 3966))
        self.assertEqual(exhausted.consumed_amounts, original.basis)
        self.assertEqual(exhausted.remaining_amounts, cents(0, 0, 0))
        self.assertEqual(original.consumed_gross, 0)
        self.assertEqual(first.tax + second.tax + last.tax, 1900)

    def test_partial_return_combines_exact_cents_with_unspent_original_rest(self):
        _, _, _, previous = self.original_two_lots()
        reopened = previous.reopen_with_return('refund-line-1', cents(1111, 211, 1322))
        self.assertEqual(reopened.basis, cents(4444, 844, 5288))
        self.assertEqual(reopened.consumed_gross, 0)
        self.assertEqual(previous.remaining_amounts, cents(3333, 633, 3966))
        self.assertEqual(previous.applied_return_ids, frozenset())
        first, partly_spent = reopened.consume(2644)
        second, exhausted = partly_spent.consume(2644)
        self.assertEqual(first, cents(2222, 422, 2644))
        self.assertEqual(second, first)
        self.assertEqual(exhausted.remaining_amounts, cents(0, 0, 0))

    def test_repeated_partial_returns_after_new_consumption_preserve_all_cents(self):
        # Each row combines the explicitly returned portions of the two original
        # 3967-cent lots. The middle row carries their different rounding cent.
        _, _, _, state = self.original_two_lots()
        state = state.reopen_with_return('return-1', cents(2222, 422, 2644))
        self.assertEqual(state.basis, cents(5555, 1055, 6610))
        first, state = state.consume(1000)
        self.assertEqual(first, cents(840, 160, 1000))
        self.assertEqual(state.remaining_amounts, cents(4715, 895, 5610))
        state = state.reopen_with_return('return-2', cents(2221, 423, 2644))
        self.assertEqual(state.basis, cents(6936, 1318, 8254))
        second, state = state.consume(2000)
        self.assertEqual(second, cents(1681, 319, 2000))
        self.assertEqual(state.remaining_amounts, cents(5255, 999, 6254))
        state = state.reopen_with_return('return-3', cents(2224, 422, 2646))
        self.assertEqual(state.basis, cents(7479, 1421, 8900))
        final, state = state.consume(8900)
        self.assertEqual(final, cents(7479, 1421, 8900))
        self.assertEqual(first.net + second.net + final.net, 10000)
        self.assertEqual(first.tax + second.tax + final.tax, 1900)
        self.assertEqual(state.remaining_amounts, cents(0, 0, 0))
        self.assertEqual(state.applied_return_ids, frozenset(('return-1', 'return-2', 'return-3')))

    def test_full_returns_restore_original_capacity_without_editing_original_lots(self):
        original, first, second, previous = self.original_two_lots()
        one = previous.reopen_with_return('first-lot', first)
        self.assertEqual(one.basis, cents(6667, 1266, 7933))
        two = one.reopen_with_return('second-lot', second)
        self.assertEqual(two.basis, original.basis)
        self.assertEqual(previous.consumed_gross, 7934)
        self.assertEqual((first, second), (cents(3334, 633, 3967), cents(3333, 634, 3967)))

    def test_returned_lot_cents_are_not_recalculated_from_invoice_rate(self):
        exhausted = ComponentSegment(cents(10000, 1900, 11900), consumed_gross=11900)
        reopened = exhausted.reopen_with_return('second-lot', cents(3333, 634, 3967))
        allocation, empty = reopened.consume(3967)
        self.assertEqual(allocation, cents(3333, 634, 3967))
        self.assertEqual(empty.remaining_amounts, cents(0, 0, 0))
        # Reapplying the invoice's 19% rate to 39.67 would instead give 6.33.
        self.assertEqual((Decimal('39.67') * Decimal(19) / Decimal(119)).quantize(
            Decimal('.01'), rounding=ROUND_HALF_UP), Decimal('6.33'))

    def test_duplicate_return_rejected_after_consumption_and_later_reopen(self):
        state = ComponentSegment(cents(0, 0, 0)).reopen_with_return('immutable-line', cents(2, 1, 3))
        _, state = state.consume(1)
        state = state.reopen_with_return('another-line', cents(1, 0, 1))
        for amount in (cents(2, 1, 3), cents(1, 0, 1)):
            with self.subTest(amount=amount), self.assertRaisesRegex(ValueError, 'already applied'):
                state.reopen_with_return('immutable-line', amount)
        self.assertEqual(state.applied_return_ids, frozenset(('immutable-line', 'another-line')))

    def test_zero_empty_and_full_tax_segments_do_not_divide_by_zero(self):
        empty = ComponentSegment(cents(0, 0, 0))
        self.assertEqual(empty.consumed_amounts, cents(0, 0, 0))
        self.assertEqual(empty.remaining_amounts, cents(0, 0, 0))
        with self.assertRaises(ValueError):
            empty.consume(1)
        for basis, expected in ((cents(7, 0, 7), cents(3, 0, 3)),
                                (cents(0, 7, 7), cents(0, 3, 3))):
            with self.subTest(basis=basis):
                reopened = empty.reopen_with_return('documented-line', basis)
                allocation, state = reopened.consume(3)
                self.assertEqual(allocation, expected)
                last, state = state.consume(4)
                self.assertEqual(allocation.net + last.net, basis.net)
                self.assertEqual(allocation.tax + last.tax, basis.tax)
                self.assertEqual(state.remaining_amounts, cents(0, 0, 0))

    def test_half_cent_rounds_up_then_preserves_final_cent(self):
        state = ComponentSegment(cents(1, 1, 2))
        first, state = state.consume(1)
        last, state = state.consume(1)
        self.assertEqual(first, cents(0, 1, 1))
        self.assertEqual(last, cents(1, 0, 1))
        self.assertEqual(state.consumed_amounts, cents(1, 1, 2))

    def test_small_segment_paths_match_independent_decimal_rounding_and_conserve(self):
        for net in range(7):
            for tax in range(7):
                gross = net + tax
                if gross == 0:
                    continue
                with self.subTest(net=net, tax=tax):
                    state = ComponentSegment(cents(net, tax, gross))
                    total_net = total_tax = 0
                    for consumed in range(1, gross + 1):
                        allocation, state = state.consume(1)
                        total_net += allocation.net
                        total_tax += allocation.tax
                        with localcontext() as context:
                            context.prec = 30
                            expected_tax = (Decimal(consumed) * Decimal(tax) / Decimal(gross)).quantize(
                                Decimal(1), rounding=ROUND_HALF_UP)
                        self.assertEqual(total_tax, int(expected_tax))
                        self.assertEqual(total_net + total_tax, consumed)
                        self.assertGreaterEqual(allocation.net, 0)
                        self.assertGreaterEqual(allocation.tax, 0)
                    self.assertEqual((total_net, total_tax), (net, tax))
                    self.assertEqual(state.remaining_amounts, cents(0, 0, 0))

    def test_unbounded_integer_precision_is_preserved(self):
        unit = 10 ** 80 + 1
        basis = cents(unit, unit, 2 * unit)
        state = ComponentSegment(basis)
        first, state = state.consume(1)
        middle, state = state.consume(2 * unit - 2)
        last, state = state.consume(1)
        self.assertEqual(first, cents(0, 1, 1))
        self.assertEqual(middle, cents(unit - 1, unit - 1, 2 * unit - 2))
        self.assertEqual(last, cents(1, 0, 1))
        self.assertEqual(state.consumed_amounts, basis)
        restored = state.reopen_with_return('huge-exact-lot', basis)
        self.assertEqual(restored.basis, basis)

    def test_amount_and_state_inputs_require_exact_nonnegative_integer_cents(self):
        for invalid in (True, False, -1, 1.0, '1', Decimal(1), None):
            for name in ('net', 'tax', 'gross'):
                values = dict(net=1, tax=1, gross=2)
                values[name] = invalid
                with self.subTest(field=name, value=invalid), self.assertRaises(ValueError):
                    CentAmounts(**values)
            with self.subTest(consumed=invalid), self.assertRaises(ValueError):
                ComponentSegment(cents(2, 1, 3), consumed_gross=invalid)
        with self.assertRaises(ValueError):
            CentAmounts(net=1, tax=1, gross=3)
        with self.assertRaises(ValueError):
            ComponentSegment({'net': 2, 'tax': 1, 'gross': 3})
        with self.assertRaises(ValueError):
            ComponentSegment(cents(2, 1, 3), consumed_gross=4)

    def test_invalid_allocation_and_return_cannot_change_prior_state(self):
        state = ComponentSegment(cents(2, 1, 3))
        for invalid in (True, False, 0, -1, 4, 1.0, '1', Decimal(1), None):
            with self.subTest(amount=invalid), self.assertRaises(ValueError):
                state.consume(invalid)
        for invalid in ('', ' identity', 'identity ', '\n', None, True, 12):
            with self.subTest(identity=invalid), self.assertRaises(ValueError):
                state.reopen_with_return(invalid, cents(1, 0, 1))
        for invalid in (cents(0, 0, 0), None, True, {'net': 1, 'tax': 0, 'gross': 1}):
            with self.subTest(returned=invalid), self.assertRaises(ValueError):
                state.reopen_with_return('identity', invalid)
        self.assertEqual(state, ComponentSegment(cents(2, 1, 3)))

    def test_return_identity_history_and_values_are_immutable(self):
        for invalid in (set(), [], ('return-1',), frozenset(('',)), frozenset((True,)),
                        frozenset((' trailing ',))):
            with self.subTest(identities=invalid), self.assertRaises(ValueError):
                ComponentSegment(cents(1, 0, 1), applied_return_ids=invalid)
        basis = cents(1, 0, 1)
        state = ComponentSegment(basis, applied_return_ids=frozenset(('return-1',)))
        with self.assertRaises(FrozenInstanceError):
            state.consumed_gross = 1
        with self.assertRaises(FrozenInstanceError):
            basis.net = 2


if __name__ == '__main__':
    unittest.main()
