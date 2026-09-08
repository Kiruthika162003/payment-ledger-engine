"""The trial balance: every account in its column, the two columns equal.

A trial balance is the oldest check in bookkeeping and still the
sharpest: list every account's net movement in the debit column if
it is a net debit and the credit column if it is a net credit, sum
the two columns, and they are equal or the books are broken. The
elegance is that this needs nothing but the postings, not the
account types, because the column an account lands in is decided by
the sign of its debits minus its credits, and the columns must
match for the trivial reason that every entry contributed equally
to both. This module builds the report per currency, since summing
a dollar column and a yen column into one total is the kind of
nonsense a trial balance exists to catch, and it filters accounts
to the currency they were opened in so each report is internally
comparable. The report keeps a zero-balance account out of the
listing by default, because a trial balance is read to find what
moved and pages of zeros bury it, but the totals it reports are
over every account so the equality it claims is the real one.
"""

from __future__ import annotations

from dataclasses import dataclass

from mint.ledger import Ledger


@dataclass(frozen=True)
class TrialLine:
    code: str
    name: str
    debit: int
    credit: int


@dataclass(frozen=True)
class TrialBalance:
    currency: str
    lines: tuple[TrialLine, ...]
    total_debit: int
    total_credit: int

    def balances(self) -> bool:
        return self.total_debit == self.total_credit

    def difference(self) -> int:
        return self.total_debit - self.total_credit


def trial_balance(ledger: Ledger, currency: str, include_zero: bool = False) -> TrialBalance:
    currency = currency.upper()
    lines: list[TrialLine] = []
    total_debit = 0
    total_credit = 0
    for code in sorted(ledger.chart.accounts):
        account = ledger.chart.get(code)
        if account.currency != currency:
            continue
        net = ledger.raw_debits(code) - ledger.raw_credits(code)
        debit = net if net > 0 else 0
        credit = -net if net < 0 else 0
        total_debit += debit
        total_credit += credit
        if net == 0 and not include_zero:
            continue
        lines.append(TrialLine(code, account.name, debit, credit))
    return TrialBalance(
        currency=currency,
        lines=tuple(lines),
        total_debit=total_debit,
        total_credit=total_credit,
    )
