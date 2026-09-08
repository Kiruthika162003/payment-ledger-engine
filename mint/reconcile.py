"""Reconciliation: matching the ledger against the bank, and naming what will not match.

Reconciliation is the discipline of proving that the ledger and
the bank agree, and its value is entirely in what it refuses to
match. A reconciler that pairs things too eagerly produces a clean
report that hides a missing deposit; the honest one matches only
what genuinely corresponds and then lists, by name, every line on
each side that found no partner, because those unmatched lines are
the whole reason to reconcile. This module matches in two passes,
strict before loose. The first pass pairs lines that agree on both
amount and reference, the unambiguous matches. The second pass
pairs a still-unmatched ledger line with a bank line of the same
amount whose date falls within a window, since a payment posted on
Friday may clear the bank on Monday, and among candidates it
prefers the nearest date so a genuine pair is not stolen by a
coincidental one further away. Amounts must match to the cent;
reconciliation never closes a gap by rounding, since a gap is
precisely the signal it exists to raise. What remains unmatched on
each side is reported in full, and a reconciliation with anything
unmatched does not call itself reconciled.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.money import Money


@dataclass(frozen=True)
class Movement:
    date: datetime.date
    amount: Money
    ref: str


@dataclass(frozen=True)
class Reconciliation:
    matched: tuple[tuple[Movement, Movement], ...]
    unmatched_ledger: tuple[Movement, ...]
    unmatched_bank: tuple[Movement, ...]

    def is_reconciled(self) -> bool:
        return not self.unmatched_ledger and not self.unmatched_bank

    def matched_count(self) -> int:
        return len(self.matched)


def reconcile(
    ledger_side: list[Movement],
    bank_side: list[Movement],
    window_days: int = 3,
) -> Reconciliation:
    bank_open = list(range(len(bank_side)))
    matched: list[tuple[Movement, Movement]] = []
    ledger_open: list[int] = []

    for li, ledger_line in enumerate(ledger_side):
        hit = _find_exact(ledger_line, bank_side, bank_open)
        if hit is None:
            ledger_open.append(li)
        else:
            bank_open.remove(hit)
            matched.append((ledger_line, bank_side[hit]))

    still_open: list[int] = []
    for li in ledger_open:
        ledger_line = ledger_side[li]
        hit = _find_windowed(ledger_line, bank_side, bank_open, window_days)
        if hit is None:
            still_open.append(li)
        else:
            bank_open.remove(hit)
            matched.append((ledger_line, bank_side[hit]))

    return Reconciliation(
        matched=tuple(matched),
        unmatched_ledger=tuple(ledger_side[i] for i in still_open),
        unmatched_bank=tuple(bank_side[i] for i in bank_open),
    )


def _find_exact(line: Movement, bank: list[Movement], open_indices: list[int]) -> int | None:
    for index in open_indices:
        candidate = bank[index]
        if candidate.amount == line.amount and candidate.ref == line.ref:
            return index
    return None


def _find_windowed(
    line: Movement, bank: list[Movement], open_indices: list[int], window_days: int
) -> int | None:
    best: int | None = None
    best_gap: int | None = None
    for index in open_indices:
        candidate = bank[index]
        if candidate.amount != line.amount:
            continue
        gap = abs((candidate.date - line.date).days)
        if gap > window_days:
            continue
        closer = best_gap is None or gap < best_gap
        tie_earlier = best_gap == gap and best is not None and candidate.date < bank[best].date
        if closer or tie_earlier:
            best = index
            best_gap = gap
    return best
