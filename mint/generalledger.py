"""The general ledger report: every account, every movement, with running balances.

The general ledger is the report an auditor asks for first, because
it is the whole book laid out account by account with each movement
in date order and a running balance beside it, which is what lets a
reader follow a number back to the transactions that produced it.
This module builds it from the entries alone, so it can never
disagree with them, and it carries the same properties the ledger
itself has: the running balance at the end of each account section
equals that account's balance computed independently, and the sum
of the closing balances across the report satisfies the same
debit-equals-credit identity the trial balance does. Accounts with
no movement in the window are included with their opening balance
and no lines, rather than omitted, because an account that was
expected to move and did not is exactly the finding a reviewer is
scanning for and dropping it from the report hides it. Each line
carries the entry's memo and reference so a reader following an
odd movement has somewhere to go next.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.ledger import Ledger
from mint.money import Money


@dataclass(frozen=True)
class LedgerLine:
    date: datetime.date
    memo: str
    ref: str
    debit: int
    credit: int
    balance: int


@dataclass(frozen=True)
class AccountSection:
    code: str
    name: str
    currency: str
    opening: int
    lines: tuple[LedgerLine, ...]
    closing: int

    def movement(self) -> int:
        return self.closing - self.opening

    def was_quiet(self) -> bool:
        return not self.lines


@dataclass(frozen=True)
class GeneralLedger:
    currency: str
    start: datetime.date
    end: datetime.date
    sections: tuple[AccountSection, ...]

    def section(self, code: str) -> AccountSection:
        for item in self.sections:
            if item.code == code:
                return item
        raise KeyError(code)

    def quiet_accounts(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.sections if item.was_quiet())

    def total_debits(self) -> int:
        return sum(line.debit for item in self.sections for line in item.lines)

    def total_credits(self) -> int:
        return sum(line.credit for item in self.sections for line in item.lines)

    def balances(self) -> bool:
        return self.total_debits() == self.total_credits()


def general_ledger(
    ledger: Ledger, currency: str, start: datetime.date, end: datetime.date
) -> GeneralLedger:
    currency = currency.upper()
    ordered = sorted(
        enumerate(ledger.entries), key=lambda pair: (pair[1].date, pair[0])
    )
    sections: list[AccountSection] = []
    for code in sorted(ledger.chart.accounts):
        account = ledger.chart.get(code)
        if account.currency != currency:
            continue
        debit_normal = account.is_debit_normal()
        opening = 0
        running = 0
        lines: list[LedgerLine] = []
        for _, item in ordered:
            for posting in item.postings_for(code):
                signed = posting.signed_for(debit_normal)
                if item.date < start:
                    opening += signed
                    running += signed
                    continue
                if item.date > end:
                    continue
                running += signed
                lines.append(
                    LedgerLine(
                        date=item.date,
                        memo=item.memo,
                        ref=item.ref,
                        debit=posting.debit_units(),
                        credit=posting.credit_units(),
                        balance=running,
                    )
                )
        sections.append(
            AccountSection(
                code=code,
                name=account.name,
                currency=currency,
                opening=opening,
                lines=tuple(lines),
                closing=running,
            )
        )
    return GeneralLedger(
        currency=currency, start=start, end=end, sections=tuple(sections)
    )


def closing_money(section: AccountSection) -> Money:
    return Money.from_minor(section.closing, section.currency)
