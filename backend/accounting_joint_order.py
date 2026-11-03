"""Pure reconstruction of two journals' exact observed opposite sequence heads.

An observation records both an after and a before boundary: opposite entry k
already existed, and k+1 did not. A merge therefore requires exactly one next
observation to match the opposite cursor. Merely sorting predecessor edges
would incorrectly accept two entries that both claim to have happened first.

The caller validates database rows, proof versions, sources and permissions.
This helper does not infer missing observations, repair ordering, inspect
timestamps, or assign virtual heads to historical proof versions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


def _integer(value: int, name: str, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer of at least {minimum}')


@dataclass(frozen=True)
class HeadObservation:
    """One immutable own sequence number and its exact observed opposite head."""

    sequence: int
    other_head: int

    def __post_init__(self) -> None:
        _integer(self.sequence, 'Own sequence', 1)
        _integer(self.other_head, 'Observed opposite head', 0)


def _snapshot(values: Iterable[HeadObservation]) -> tuple[HeadObservation, ...]:
    try:
        result = tuple(values)
    except TypeError:
        raise ValueError('A finite iterable of HeadObservation values is required') from None
    if any(type(value) is not HeadObservation for value in result):
        raise ValueError('Each stream member must be a HeadObservation')
    return result


def _validate(values: tuple[HeadObservation, ...], opposite_length: int) -> None:
    previous = 0
    for sequence, value in enumerate(values, 1):
        # Validate again at this boundary rather than relying on construction
        # alone when a caller supplies observations from untrusted storage.
        _integer(value.sequence, 'Own sequence', 1)
        _integer(value.other_head, 'Observed opposite head', 0)
        if value.sequence != sequence:
            raise ValueError('Own sequences must be supplied exactly as 1 through N')
        if value.other_head < previous:
            raise ValueError('Observed opposite heads must not regress')
        if value.other_head > opposite_length:
            raise ValueError('Observed opposite head exceeds the complete opposite stream')
        previous = value.other_head


def merge_observed_heads(
        left: Iterable[HeadObservation], right: Iterable[HeadObservation],
) -> tuple[tuple[Literal['left', 'right'], HeadObservation], ...]:
    """Return the unique joint order, or raise ValueError for inconsistent heads.

    Both supplied streams must be complete, ordered and contiguous from one.
    Each opposite head is a nonnegative integer bounded by the other stream's
    length; heads in either stream must be monotone. Booleans are not integers
    for this contract. Inputs are preserved, and the returned tuple refers to
    their original frozen observations.

    A historical virtual head, such as zero for an old positive proof, must be
    supplied explicitly by the caller. No journal or version has precedence.
    Runtime and auxiliary storage are linear in the combined stream lengths.
    """
    left_values, right_values = _snapshot(left), _snapshot(right)
    _validate(left_values, len(right_values))
    _validate(right_values, len(left_values))
    left_cursor = right_cursor = 0
    result = []
    while left_cursor < len(left_values) or right_cursor < len(right_values):
        left_ready = left_cursor < len(left_values) and left_values[left_cursor].other_head == right_cursor
        right_ready = right_cursor < len(right_values) and right_values[right_cursor].other_head == left_cursor
        if left_ready and right_ready:
            raise ValueError('Both next observations claim to precede the other')
        if not left_ready and not right_ready:
            raise ValueError('No next observation matches the exact opposite cursor')
        if left_ready:
            result.append(('left', left_values[left_cursor]))
            left_cursor += 1
        else:
            result.append(('right', right_values[right_cursor]))
            right_cursor += 1
    return tuple(result)
