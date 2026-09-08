"""Intercompany balances: the transactions a group must delete from its own accounts.

When one company in a group sells to another, both books record a
real transaction, but from the group's point of view nothing
happened: the group sold to itself. Consolidating without removing
those transactions inflates group revenue and group receivables by
the same amount, which is the oldest way to make a group look
larger than it is. This module tracks intercompany balances as
pairs and produces the elimination entries that remove them. The
control that makes the elimination trustworthy is reciprocity: for
every receivable one entity records against another, the other
should record a matching payable, and any difference between the
two is a real problem, usually an invoice booked in one book and
not the other, or booked at a different amount. So the module
reports mismatches by pair with the difference rather than
eliminating whichever number it happened to see first, because
silently eliminating an unmatched balance hides the discrepancy and
leaves the consolidated books out of balance by exactly the amount
nobody noticed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class IntercompanyBalance:
    holder: str
    counterparty: str
    amount: Money
    kind: str


@dataclass(frozen=True)
class Mismatch:
    pair: tuple[str, str]
    receivable: Money
    payable: Money

    def difference(self) -> Money:
        return self.receivable - self.payable


@dataclass
class IntercompanyLedger:
    currency: str
    balances: list[IntercompanyBalance] = field(default_factory=list)

    def record(
        self, holder: str, counterparty: str, amount: Money, kind: str
    ) -> IntercompanyBalance:
        if amount.currency != self.currency:
            raise Refused(
                f"this intercompany ledger is in {self.currency}, not "
                f"{amount.currency}"
            )
        if holder == counterparty:
            raise Refused("an entity cannot hold an intercompany balance with itself")
        if kind not in ("receivable", "payable"):
            raise Refused(f"{kind!r} is not an intercompany kind")
        if not amount.is_positive():
            raise Refused("an intercompany balance is a positive amount")
        item = IntercompanyBalance(holder, counterparty, amount, kind)
        self.balances.append(item)
        return item

    def _total(self, holder: str, counterparty: str, kind: str) -> Money:
        total = Money.zero(self.currency)
        for item in self.balances:
            matches = (
                item.holder == holder
                and item.counterparty == counterparty
                and item.kind == kind
            )
            if matches:
                total = total + item.amount
        return total

    def pairs(self) -> list[tuple[str, str]]:
        seen: set[tuple[str, str]] = set()
        for item in self.balances:
            seen.add(tuple(sorted((item.holder, item.counterparty))))
        return sorted(seen)

    def mismatches(self) -> list[Mismatch]:
        found: list[Mismatch] = []
        for left, right in self.pairs():
            receivable = self._total(left, right, "receivable") + self._total(
                right, left, "receivable"
            )
            payable = self._total(left, right, "payable") + self._total(
                right, left, "payable"
            )
            if receivable != payable:
                found.append(Mismatch((left, right), receivable, payable))
        return found

    def is_reciprocal(self) -> bool:
        return not self.mismatches()

    def eliminable(self) -> Money:
        # Only matched balances are eliminated; a mismatch is reported, never
        # quietly removed at whichever figure happened to be seen first.
        total = Money.zero(self.currency)
        mismatched = {m.pair for m in self.mismatches()}
        for left, right in self.pairs():
            if (left, right) in mismatched:
                continue
            total = total + self._total(left, right, "receivable")
            total = total + self._total(right, left, "receivable")
        return total
