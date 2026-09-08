"""Account statements: opening balance, the movements, the running total, the close.

A statement answers the question a person actually asks about an
account: where did it start this period, what happened, and where
did it end. This module builds that from the ledger by folding the
postings in date order. The opening balance is the account's
signed balance from every posting dated before the period, so the
statement stands on its own without the reader having to know the
prior history; the closing balance is the opening plus the
period's movements, and it equals the account's balance as of the
period end computed independently, a redundancy the tests exploit
to catch a fold that drifts. Each line carries the movement on the
side it fell and the running balance after it, in the account's
natural direction, so a debit-normal account reads as growing when
debited and a credit-normal account reads as growing when
credited, which is what makes a statement legible to someone who
does not think in debits and credits. Entries are folded in date
order with ties broken by the order they were posted, because two
movements on the same day still happened in some sequence and a
statement that reorders them tells a small lie about the day.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.ledger import Ledger
from mint.money import Money


@dataclass(frozen=True)
class StatementLine:
    date: datetime.date
    memo: str
    ref: str
    debit: int
    credit: int
    balance: int


@dataclass(frozen=True)
class Statement:
    code: str
    currency: str
    start: datetime.date
    end: datetime.date
    opening: Money
    closing: Money
    lines: tuple[StatementLine, ...]

    def movement(self) -> Money:
        return self.closing - self.opening

    def line_count(self) -> int:
        return len(self.lines)


def _ordered(ledger: Ledger) -> list[tuple[int, object]]:
    return sorted(enumerate(ledger.entries), key=lambda pair: (pair[1].date, pair[0]))


def statement(
    ledger: Ledger, code: str, start: datetime.date, end: datetime.date
) -> Statement:
    account = ledger.chart.get(code)
    debit_normal = account.is_debit_normal()
    opening_units = 0
    running = 0
    lines: list[StatementLine] = []
    for _, entry in _ordered(ledger):
        for posting in entry.postings_for(code):
            signed = posting.signed_for(debit_normal)
            if entry.date < start:
                opening_units += signed
                running += signed
                continue
            if entry.date > end:
                continue
            running += signed
            lines.append(
                StatementLine(
                    date=entry.date,
                    memo=entry.memo,
                    ref=entry.ref,
                    debit=posting.debit_units(),
                    credit=posting.credit_units(),
                    balance=running,
                )
            )
    return Statement(
        code=code,
        currency=account.currency,
        start=start,
        end=end,
        opening=Money.from_minor(opening_units, account.currency),
        closing=Money.from_minor(running, account.currency),
        lines=tuple(lines),
    )
