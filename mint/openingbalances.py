"""Opening balances: starting a new ledger from an old one without importing its errors.

Migrating to a new ledger means loading the closing balances of the
old one as opening balances of the new, and the moment of the
migration is the only chance to prove the numbers before they
become history. Two checks matter. The balances must sum to zero
across all accounts, since a set that does not is a set the old
system was already wrong about, and importing it silently makes the
new ledger wrong from its first day. And every account referenced
must exist in the new chart, because a balance for an account that
was renamed or merged has to be mapped deliberately rather than
dropped. This module runs both checks before posting anything and
reports every problem at once, since a migration is done under time
pressure and finding the issues one at a time is the difference
between an evening and a week. The import posts a single balanced
opening entry against an equity suspense account, so the migration
appears in the ledger as one traceable event rather than a hundred
mysterious first postings.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.entry import Entry, entry
from mint.errors import Refused
from mint.ledger import Ledger
from mint.money import Money
from mint.posting import credit, debit


@dataclass(frozen=True)
class OpeningLine:
    account: str
    amount: Money

    def is_debit(self) -> bool:
        return self.amount.is_positive()


@dataclass(frozen=True)
class MigrationProblem:
    account: str
    reason: str


@dataclass
class OpeningBalanceSet:
    currency: str
    as_of: datetime.date
    lines: list[OpeningLine] = field(default_factory=list)

    def add(self, account: str, amount: Money) -> OpeningLine:
        if amount.currency != self.currency:
            raise Refused(
                f"the opening balance for {account!r} is in {amount.currency}, "
                f"not {self.currency}"
            )
        if any(existing.account == account for existing in self.lines):
            raise Refused(f"account {account!r} already has an opening balance")
        line = OpeningLine(account, amount)
        self.lines.append(line)
        return line

    def net(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.amount
        return total

    def balances(self) -> bool:
        return self.net().is_zero()

    def validate(self, ledger: Ledger) -> list[MigrationProblem]:
        problems: list[MigrationProblem] = []
        for line in self.lines:
            if not ledger.chart.has(line.account):
                problems.append(
                    MigrationProblem(
                        line.account,
                        "the account is not in the new chart; a renamed or "
                        "merged account has to be mapped deliberately",
                    )
                )
                continue
            account = ledger.chart.get(line.account)
            if account.currency != self.currency:
                problems.append(
                    MigrationProblem(
                        line.account,
                        f"the account holds {account.currency} but the opening "
                        f"balance is in {self.currency}",
                    )
                )
        if not self.balances():
            problems.append(
                MigrationProblem(
                    "(all)",
                    f"the balances net to {self.net().format()} rather than "
                    "zero; the old system was already wrong about this",
                )
            )
        return problems

    def is_importable(self, ledger: Ledger) -> bool:
        return not self.validate(ledger)

    def build_entry(self, suspense_account: str) -> Entry:
        if not self.lines:
            raise Refused("an opening balance set with no lines imports nothing")
        postings = []
        for line in self.lines:
            if line.amount.is_zero():
                continue
            if line.is_debit():
                postings.append(debit(line.account, line.amount))
            else:
                postings.append(credit(line.account, -line.amount))
        if not postings:
            raise Refused("every opening balance is zero; there is nothing to post")
        net = self.net()
        if not net.is_zero():
            # The suspense leg exists so an unbalanced set can be posted
            # deliberately after someone has looked at it, never silently.
            if net.is_positive():
                postings.append(credit(suspense_account, net))
            else:
                postings.append(debit(suspense_account, -net))
        return entry(
            postings,
            self.as_of,
            memo="opening balances",
            ref="MIGRATION",
            tags=frozenset({"opening"}),
        )

    def post_into(self, ledger: Ledger, suspense_account: str) -> Entry:
        problems = self.validate(ledger)
        blocking = [item for item in problems if item.account != "(all)"]
        if blocking:
            raise Refused(
                f"{len(blocking)} account(s) cannot be migrated: "
                f"{[item.account for item in blocking]}"
            )
        return ledger.post(self.build_entry(suspense_account))
