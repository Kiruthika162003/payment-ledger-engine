"""Cash flow: where the cash actually came from and went, over a period.

Profit is an opinion and cash is a fact, which is why a business
that is profitable on the income statement can still fail to make
payroll, and the cash flow statement is what tells the two apart.
This module builds the direct-method statement: it looks at every
entry in the period that touched a cash account and attributes the
cash movement to the other accounts in the entry. The attribution
is exact rather than heuristic, because an entry balances, so the
cash side of it equals the sum of the non-cash sides, and each
non-cash posting's credit-minus-debit is precisely its
contribution to the change in cash. A non-cash credit is a source,
revenue earned or a loan drawn or a bill left unpaid, and a
non-cash debit is a use, an asset bought or an expense paid or a
debt retired. An entry that moves cash only between cash accounts
nets to zero and is dropped, since sweeping the checking account
into savings is not a cash flow of the business. The net change the
statement reports is reconciled against the plain difference
between opening and closing cash, and when the two disagree the
statement is wrong, which is the check the assays make.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.ledger import Ledger
from mint.money import Money


@dataclass(frozen=True)
class CashFlow:
    currency: str
    start: datetime.date
    end: datetime.date
    sources: tuple[tuple[str, int], ...]
    uses: tuple[tuple[str, int], ...]
    opening: Money
    closing: Money

    def total_sources(self) -> int:
        return sum(units for _, units in self.sources)

    def total_uses(self) -> int:
        return sum(units for _, units in self.uses)

    def net_change(self) -> Money:
        return Money.from_minor(self.total_sources() - self.total_uses(), self.currency)

    def reconciles(self) -> bool:
        return self.net_change() == self.closing - self.opening


def _cash_balance(
    ledger: Ledger,
    cash_accounts: list[str],
    before: datetime.date | None,
    inclusive_end: datetime.date | None,
) -> int:
    total = 0
    for code in cash_accounts:
        for entry in ledger.entries:
            if before is not None and entry.date >= before:
                continue
            if inclusive_end is not None and entry.date > inclusive_end:
                continue
            for posting in entry.postings_for(code):
                total += posting.debit_units() - posting.credit_units()
    return total


def cash_flow(
    ledger: Ledger,
    cash_accounts: list[str],
    currency: str,
    start: datetime.date,
    end: datetime.date,
) -> CashFlow:
    currency = currency.upper()
    cash_set = set(cash_accounts)
    sources: dict[str, int] = {}
    uses: dict[str, int] = {}

    for entry in ledger.entries:
        if entry.date < start or entry.date > end:
            continue
        cash_delta = sum(
            p.debit_units() - p.credit_units()
            for p in entry.postings
            if p.account in cash_set
        )
        if cash_delta == 0:
            continue
        for posting in entry.postings:
            if posting.account in cash_set:
                continue
            contribution = posting.credit_units() - posting.debit_units()
            if contribution > 0:
                sources[posting.account] = sources.get(posting.account, 0) + contribution
            elif contribution < 0:
                uses[posting.account] = uses.get(posting.account, 0) - contribution

    opening = _cash_balance(ledger, cash_accounts, start, None)
    closing = _cash_balance(ledger, cash_accounts, None, end)
    return CashFlow(
        currency=currency,
        start=start,
        end=end,
        sources=tuple(sorted(sources.items())),
        uses=tuple(sorted(uses.items())),
        opening=Money.from_minor(opening, currency),
        closing=Money.from_minor(closing, currency),
    )
