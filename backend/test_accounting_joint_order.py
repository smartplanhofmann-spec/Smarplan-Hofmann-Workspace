"""Independent small interleaving oracles for exact opposite-head ordering."""
from dataclasses import FrozenInstanceError
from itertools import combinations, combinations_with_replacement, product
import unittest

from accounting_joint_order import HeadObservation, merge_observed_heads


def actual_orders(left_count, right_count):
    """Enumerate actual serial histories, without consulting observed heads."""
    length = left_count+right_count
    for left_positions in combinations(range(length), left_count):
        positions = frozenset(left_positions)
        yield tuple('left' if position in positions else 'right' for position in range(length))


def observations_from_history(order):
    """Capture the head visible immediately before each actual operation."""
    left, right = [], []
    for side in order:
        if side == 'left':
            left.append(HeadObservation(len(left)+1, len(right)))
        else:
            right.append(HeadObservation(len(right)+1, len(left)))
    return left, right


class JointOrderTests(unittest.TestCase):
    def test_every_actual_interleaving_up_to_five_operations_per_stream_is_reconstructed(self):
        checked = 0
        for left_count, right_count in product(range(6), repeat=2):
            for order in actual_orders(left_count, right_count):
                left, right = observations_from_history(order)
                with self.subTest(order=order):
                    merged = merge_observed_heads(left, right)
                    self.assertIsInstance(merged, tuple)
                    self.assertEqual(tuple(side for side, unused in merged), order)
                    self.assertEqual(tuple(value for side, value in merged if side == 'left'), tuple(left))
                    self.assertEqual(tuple(value for side, value in merged if side == 'right'), tuple(right))
                checked += 1
        self.assertEqual(checked, 923)

    def test_all_small_bounded_monotone_head_pairs_match_the_independent_history_oracle(self):
        checked = accepted = 0
        for left_count, right_count in product(range(4), repeat=2):
            oracle = {}
            for order in actual_orders(left_count, right_count):
                left, right = observations_from_history(order)
                key = tuple(value.other_head for value in left), tuple(value.other_head for value in right)
                self.assertNotIn(key, oracle)
                oracle[key] = order
            for left_heads in combinations_with_replacement(range(right_count+1), left_count):
                for right_heads in combinations_with_replacement(range(left_count+1), right_count):
                    left = tuple(HeadObservation(index, head) for index, head in enumerate(left_heads, 1))
                    right = tuple(HeadObservation(index, head) for index, head in enumerate(right_heads, 1))
                    key = left_heads, right_heads
                    with self.subTest(left=left_heads, right=right_heads):
                        if key in oracle:
                            self.assertEqual(tuple(side for side, unused in merge_observed_heads(left, right)), oracle[key])
                            accepted += 1
                        else:
                            with self.assertRaises(ValueError):
                                merge_observed_heads(left, right)
                    checked += 1
        self.assertEqual((checked, accepted), (697, 69))

    def test_two_zero_heads_cannot_both_claim_to_have_been_first(self):
        with self.assertRaisesRegex(ValueError, 'Both next observations'):
            merge_observed_heads([HeadObservation(1, 0)], [HeadObservation(1, 0)])

    def test_mutual_future_heads_have_no_possible_first_operation(self):
        with self.assertRaisesRegex(ValueError, 'No next observation'):
            merge_observed_heads([HeadObservation(1, 1)], [HeadObservation(1, 1)])

    def test_contradiction_after_a_valid_prefix_is_not_silently_resolved(self):
        left = [HeadObservation(1, 0), HeadObservation(2, 1)]
        right = [HeadObservation(1, 1), HeadObservation(2, 1)]
        with self.assertRaisesRegex(ValueError, 'Both next observations'):
            merge_observed_heads(left, right)

    def test_stale_head_cannot_ignore_a_real_opposite_operation(self):
        left = [HeadObservation(1, 0), HeadObservation(2, 0)]
        right = [HeadObservation(1, 1)]
        with self.assertRaises(ValueError):
            merge_observed_heads(left, right)

    def test_regressing_heads_are_rejected_without_reordering(self):
        for left, right in (([HeadObservation(1, 1), HeadObservation(2, 0)], [HeadObservation(1, 0)]),
                            ([HeadObservation(1, 0)], [HeadObservation(1, 1), HeadObservation(2, 0)])):
            with self.subTest(left=left, right=right), self.assertRaisesRegex(ValueError, 'must not regress'):
                merge_observed_heads(left, right)

    def test_future_or_missing_opposite_heads_are_rejected(self):
        cases = (([HeadObservation(1, 1)], []), ([], [HeadObservation(1, 1)]),
                 ([HeadObservation(1, 2)], [HeadObservation(1, 0)]),
                 ([HeadObservation(1, 0)], [HeadObservation(1, 2)]))
        for left, right in cases:
            with self.subTest(left=left, right=right), self.assertRaisesRegex(ValueError, 'exceeds'):
                merge_observed_heads(left, right)

    def test_own_duplicate_missing_and_out_of_order_sequences_are_rejected(self):
        cases = ([HeadObservation(2, 0)], [HeadObservation(1, 0), HeadObservation(1, 0)],
                 [HeadObservation(1, 0), HeadObservation(3, 0)], [HeadObservation(2, 0), HeadObservation(1, 0)])
        for stream in cases:
            for left, right in ((stream, []), ([], stream)):
                with self.subTest(left=left, right=right), self.assertRaisesRegex(ValueError, 'exactly as 1 through N'):
                    merge_observed_heads(left, right)

    def test_empty_streams_and_terminal_opposite_head(self):
        self.assertEqual(merge_observed_heads([], []), ())
        for side in ('left', 'right'):
            stream = [HeadObservation(1, 0), HeadObservation(2, 0)]
            args = (stream, []) if side == 'left' else ([], stream)
            self.assertEqual(merge_observed_heads(*args), tuple((side, value) for value in stream))
        left = [HeadObservation(1, 0)]
        right = [HeadObservation(1, 1), HeadObservation(2, 1), HeadObservation(3, 1)]
        self.assertEqual(tuple(side for side, unused in merge_observed_heads(left, right)), ('left', 'right', 'right', 'right'))

    def test_integer_contract_rejects_booleans_negative_and_noninteger_values(self):
        for value in (True, False, 0, -1, 1.0, '1', None):
            with self.subTest(sequence=value), self.assertRaises(ValueError):
                HeadObservation(value, 0)
        for value in (True, False, -1, 0.0, '0', None):
            with self.subTest(other_head=value), self.assertRaises(ValueError):
                HeadObservation(1, value)

    def test_only_typed_observations_are_accepted(self):
        for stream in (None, [dict(sequence=1, other_head=0)], [(1, 0)], [True], 'observation'):
            with self.subTest(stream=stream), self.assertRaises(ValueError):
                merge_observed_heads(stream, [])

    def test_inputs_and_observations_remain_immutable_on_success_and_failure(self):
        left, right = observations_from_history(('left', 'right', 'right', 'left'))
        before = list(left), list(right)
        merged = merge_observed_heads(left, right)
        self.assertEqual((left, right), before)
        for side, value in merged:
            self.assertIs(value, (left if side == 'left' else right)[value.sequence-1])
        with self.assertRaises(FrozenInstanceError):
            left[0].other_head = 10
        invalid = [HeadObservation(1, 0)]
        with self.assertRaises(ValueError):
            merge_observed_heads(invalid, invalid)
        self.assertEqual(invalid, [HeadObservation(1, 0)])


if __name__ == '__main__':
    unittest.main()
