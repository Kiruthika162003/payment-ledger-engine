"""Snapshots: freezing what the books said, so a later report can be compared to it.

A published report is a claim about a moment, and when the same
report run later gives different numbers somebody needs to know
why. A snapshot captures the balances as of a date, with the entry
count that produced them, so a later run can be compared against
what was actually published rather than against memory. The
comparison is the useful part: it reports which accounts moved and
by how much, which is exactly the list a controller wants when the
March report changes in June. Because entries are append-only, a
difference always has a cause, either an entry backdated into the
snapshot's window or an account added since, and the diff separates
those two cases rather than presenting one list of surprises. A
snapshot stores balances rather than a copy of the ledger, which
keeps it small and makes clear that it is evidence about a report
rather than a restore point; restoring a ledger from a snapshot
would be rewriting history, which this package refuses to do
anywhere.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.ledger import Ledger
from mint.money import Money


@dataclass(frozen=True)
class Snapshot:
    label: str
    as_of: datetime.date
    taken_at: datetime.datetime
    balances: tuple[tuple[str, int], ...]
    entry_count: int
    currency: str

    def balance_of(self, code: str) -> int | None:
        for account, units in self.balances:
            if account == code:
                return units
        return None

    def accounts(self) -> tuple[str, ...]:
        return tuple(code for code, _ in self.balances)

    def total(self) -> Money:
        return Money.from_minor(sum(units for _, units in self.balances), self.currency)


@dataclass(frozen=True)
class SnapshotDiff:
    changed: tuple[tuple[str, int, int], ...]
    added_accounts: tuple[str, ...]
    removed_accounts: tuple[str, ...]
    entries_added: int

    def is_identical(self) -> bool:
        return (
            not self.changed
            and not self.added_accounts
            and not self.removed_accounts
        )

    def largest_change(self) -> tuple[str, int, int] | None:
        if not self.changed:
            return None
        return max(self.changed, key=lambda row: abs(row[2] - row[1]))


def take(
    ledger: Ledger,
    label: str,
    as_of: datetime.date,
    taken_at: datetime.datetime,
    currency: str,
) -> Snapshot:
    currency = currency.upper()
    balances = []
    for code in sorted(ledger.chart.accounts):
        account = ledger.chart.get(code)
        if account.currency != currency:
            continue
        balances.append((code, ledger.balance_units_asof(code, as_of)))
    return Snapshot(
        label=label,
        as_of=as_of,
        taken_at=taken_at,
        balances=tuple(balances),
        entry_count=ledger.entry_count(),
        currency=currency,
    )


def compare(earlier: Snapshot, later: Snapshot) -> SnapshotDiff:
    earlier_map = dict(earlier.balances)
    later_map = dict(later.balances)
    changed = []
    for code, units in later_map.items():
        if code in earlier_map and earlier_map[code] != units:
            changed.append((code, earlier_map[code], units))
    added = tuple(sorted(set(later_map) - set(earlier_map)))
    removed = tuple(sorted(set(earlier_map) - set(later_map)))
    return SnapshotDiff(
        changed=tuple(sorted(changed)),
        added_accounts=added,
        removed_accounts=removed,
        entries_added=later.entry_count - earlier.entry_count,
    )
