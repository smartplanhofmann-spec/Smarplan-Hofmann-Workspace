"""Pure versioned identities and exact cumulative returns of a fixed income lot.

The caller authenticates each lot's immutable original cents and reconstructs
its actual prior claims. This module neither discovers claims nor proves that
a supplied prior gross amount is complete. It checks that supplied prior
net/tax cents match that original basis, then returns exact cumulative deltas.
Changing the refund writer never changes the lot basis or resets its counter.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from accounting_component_segments import CentAmounts, ComponentSegment


def _identifier(value: str, length: int, name: str) -> None:
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{'+str(length)+'}', value):
        raise ValueError(f'{name} must contain exactly {length} lowercase hexadecimal characters')


@dataclass(frozen=True)
class LotIdentity:
    """A positive line's version is part of its identity, never an alias."""

    origin_version: str
    entry_id: str
    group_id: str

    def __post_init__(self) -> None:
        if type(self.origin_version) is not str or self.origin_version not in ('c1', 'c2'):
            raise ValueError('Origin version must be c1 or c2')
        _identifier(self.entry_id, 32, 'Origin entry ID')
        _identifier(self.group_id, 64, 'Group ID')


@dataclass(frozen=True)
class RefundLineIdentity:
    """One complete versioned refund line, distinct from its origin's identity."""

    refund_version: str
    refund_entry_id: str
    origin: LotIdentity

    def __post_init__(self) -> None:
        if type(self.refund_version) is not str or self.refund_version not in ('r1', 'r2'):
            raise ValueError('Refund version must be r1 or r2')
        _identifier(self.refund_entry_id, 32, 'Refund entry ID')
        if type(self.origin) is not LotIdentity:
            raise ValueError('A typed versioned lot identity is required')
        if self.refund_version == 'r1' and self.origin.origin_version != 'c1':
            raise ValueError('An r1 refund line can reference only a c1 lot')


@dataclass(frozen=True)
class ReturnedLot:
    """A fixed original lot basis and its already reconstructed return cents.

    ``previously_returned`` includes all valid previous refund versions. For a
    C1 lot this therefore includes old R1 claims before any R2 delta is taken.
    A stored, arithmetically plausible gross counter still requires independent
    chronological reconstruction from real claims by the domain validator.
    """

    basis: CentAmounts
    previously_returned: CentAmounts = CentAmounts(0, 0, 0)

    def __post_init__(self) -> None:
        if type(self.basis) is not CentAmounts or self.basis.gross == 0:
            raise ValueError('A positive exact original lot basis is required')
        if type(self.previously_returned) is not CentAmounts:
            raise ValueError('Exact prior return cents are required')
        state = ComponentSegment(self.basis, self.previously_returned.gross)
        if state.consumed_amounts != self.previously_returned:
            raise ValueError('Prior return cents do not match the original cumulative lot basis')

    @property
    def remaining_amounts(self) -> CentAmounts:
        return ComponentSegment(self.basis, self.previously_returned.gross).remaining_amounts

    def return_cents(self, gross: int) -> tuple[CentAmounts, ReturnedLot]:
        """Take one positive return against the same original basis, without reset."""
        state = ComponentSegment(self.basis, self.previously_returned.gross)
        returned, following = state.consume(gross)
        return returned, ReturnedLot(self.basis, following.consumed_amounts)
