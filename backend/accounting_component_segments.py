"""Pure cent arithmetic for a future documentary component segment writer.

This module does not register a feature, release persisted capacity, or verify a
ledger. A caller must establish the immutable origin of every returned amount,
its remaining refundable capacity, the archive ceiling, and the global order of
operations. It must also serialize writes and retain all preceding segment
proofs. A unique return ID alone is not proof that a return is valid.

Within one supplied state, return IDs prevent applying the same return twice.
Reopening starts a new basis from the exact unspent cents plus the exact returned
cents; it never rewrites the arithmetic of an earlier segment or source lot.
All amounts are integer cents. Invalid values raise ValueError.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


def _integer(value: int, name: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f'{name} must be a {"positive" if positive else "nonnegative"} integer cent amount')


def _return_id(value: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError('A nonempty, unchanged return identity is required')


@dataclass(frozen=True)
class CentAmounts:
    """One exact nonnegative documentary net/tax/gross amount, without a rate."""

    net: int
    tax: int
    gross: int

    def __post_init__(self) -> None:
        for name in ('net', 'tax', 'gross'):
            _integer(getattr(self, name), name)
        if self.net + self.tax != self.gross:
            raise ValueError('Net and tax cents must equal gross cents')


@dataclass(frozen=True)
class ComponentSegment:
    """Immutable arithmetic state, not an authenticated or committed ledger head.

    ``applied_return_ids`` belongs to the whole supplied sequence of segments,
    rather than just its current basis. Restoring that set completely and
    binding IDs to real immutable return lines is the future writer's job.
    """

    basis: CentAmounts
    consumed_gross: int = 0
    applied_return_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if type(self.basis) is not CentAmounts:
            raise ValueError('An exact CentAmounts basis is required')
        _integer(self.consumed_gross, 'Consumed gross')
        if self.consumed_gross > self.basis.gross:
            raise ValueError('Consumption exceeds the segment basis')
        if type(self.applied_return_ids) is not frozenset:
            raise ValueError('Applied return identities must be a frozenset')
        for value in self.applied_return_ids:
            _return_id(value)

    @property
    def consumed_amounts(self) -> CentAmounts:
        if self.basis.gross == 0:
            return CentAmounts(net=0, tax=0, gross=0)
        tax = (2 * self.consumed_gross * self.basis.tax + self.basis.gross) // (2 * self.basis.gross)
        return CentAmounts(net=self.consumed_gross - tax, tax=tax, gross=self.consumed_gross)

    @property
    def remaining_amounts(self) -> CentAmounts:
        consumed = self.consumed_amounts
        return CentAmounts(net=self.basis.net - consumed.net,
                           tax=self.basis.tax - consumed.tax,
                           gross=self.basis.gross - consumed.gross)

    def consume(self, gross: int) -> tuple[CentAmounts, ComponentSegment]:
        """Return this allocation's cents and a new state; leave this state intact."""
        _integer(gross, 'Allocation', positive=True)
        following = replace(self, consumed_gross=self.consumed_gross + gross)
        before, after = self.consumed_amounts, following.consumed_amounts
        allocation = CentAmounts(net=after.net - before.net, tax=after.tax - before.tax, gross=gross)
        return allocation, following

    def reopen_with_return(self, return_id: str, returned: CentAmounts) -> ComponentSegment:
        """Start a new basis using exact returned cents already verified by a caller.

        This checks duplicate identity only within the supplied state's history;
        it cannot authenticate an origin, prove an archive ceiling, or prevent a
        concurrent caller from using an older state. No amount is rate-derived.
        """
        _return_id(return_id)
        if return_id in self.applied_return_ids:
            raise ValueError('Return identity was already applied')
        if type(returned) is not CentAmounts or returned.gross == 0:
            raise ValueError('A positive exact returned amount is required')
        remaining = self.remaining_amounts
        return ComponentSegment(
            basis=CentAmounts(net=remaining.net + returned.net,
                              tax=remaining.tax + returned.tax,
                              gross=remaining.gross + returned.gross),
            applied_return_ids=self.applied_return_ids | frozenset((return_id,)))
