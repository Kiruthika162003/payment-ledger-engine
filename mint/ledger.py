"""The ledger: an append-only list of entries, with balances folded from them.

A ledger is not a table of balances that entries mutate; it is the
list of entries, and every balance is a fold over that list. This
is the design decision that makes a ledger auditable, because a
stored balance can be wrong in a way no one can reconstruct, while
a balance computed from the entries is wrong only if an entry is
wrong, and the entry is right there to inspect. Posting appends and
never edits, so history is immutable and a correction is a new
reversing entry rather than a quiet overwrite, which is what an
auditor means by a paper trail. The ledger enforces two things at
the point of posting that the entry alone cannot: that every
account named actually exists in the chart, catching a fat-fingered
code before it becomes an orphan balance, and that the currency of
each posting matches the currency the account was opened in, since
an account is single-currency by design and a euro posted to a
dollar account is the start of a position no report can add up.
Because every entry balances and posting only appends balanced
entries, the whole ledger is balanced by induction, and the global
balance check is not a hope but a theorem the assays confirm by
measurement.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from mint.chart import Chart
from mint.entry import Entry
from mint.errors import CurrencyMismatch, Refused, UnknownAccount
from mint.money import Money
from mint.posting import Posting


@dataclass
class Ledger:
    chart: Chart
    entries: list[Entry] = field(default_factory=list)

    def post(self, entry: Entry) -> Entry:
        for posting in entry.postings:
            if not self.chart.has(posting.account):
                raise UnknownAccount(
                    f"the entry posts to account {posting.account!r}, which "
                    "is not in the chart; open it before posting to it"
                )
            account = self.chart.get(posting.account)
            if posting.currency != account.currency:
                raise CurrencyMismatch(
                    f"account {account.code!r} holds {account.currency} but "
                    f"the posting is in {posting.currency}; open a separate "
                    "account for each currency you hold"
                )
        self.entries.append(entry)
        return entry

    def raw_debits(self, code: str) -> int:
        return sum(
            p.debit_units() for e in self.entries for p in e.postings_for(code)
        )

    def raw_credits(self, code: str) -> int:
        return sum(
            p.credit_units() for e in self.entries for p in e.postings_for(code)
        )

    def balance_units(self, code: str) -> int:
        account = self.chart.get(code)
        return account.signed_units(self.raw_debits(code), self.raw_credits(code))

    def balance(self, code: str) -> Money:
        account = self.chart.get(code)
        return Money.from_minor(self.balance_units(code), account.currency)

    def raw_debits_asof(self, code: str, date: datetime.date) -> int:
        return sum(
            p.debit_units()
            for e in self.entries
            if e.date <= date
            for p in e.postings_for(code)
        )

    def raw_credits_asof(self, code: str, date: datetime.date) -> int:
        return sum(
            p.credit_units()
            for e in self.entries
            if e.date <= date
            for p in e.postings_for(code)
        )

    def balance_units_asof(self, code: str, date: datetime.date) -> int:
        account = self.chart.get(code)
        return account.signed_units(
            self.raw_debits_asof(code, date), self.raw_credits_asof(code, date)
        )

    def balance_asof(self, code: str, date: datetime.date) -> Money:
        account = self.chart.get(code)
        return Money.from_minor(self.balance_units_asof(code, date), account.currency)

    def postings_for(self, code: str) -> list[tuple[Entry, Posting]]:
        self.chart.get(code)
        return [
            (entry, posting)
            for entry in self.entries
            for posting in entry.postings_for(code)
        ]

    def all_balances(self) -> dict[str, Money]:
        return {code: self.balance(code) for code in self.chart.accounts}

    def nonzero_balances(self) -> dict[str, Money]:
        return {
            code: money
            for code, money in self.all_balances().items()
            if not money.is_zero()
        }

    def total_debits(self, currency: str) -> int:
        return sum(
            p.debit_units()
            for e in self.entries
            for p in e.postings
            if p.currency == currency
        )

    def total_credits(self, currency: str) -> int:
        return sum(
            p.credit_units()
            for e in self.entries
            for p in e.postings
            if p.currency == currency
        )

    def currencies(self) -> list[str]:
        seen: set[str] = set()
        for entry in self.entries:
            seen.update(entry.currencies())
        return sorted(seen)

    def imbalance(self) -> dict[str, int]:
        net: dict[str, int] = defaultdict(int)
        for currency in self.currencies():
            difference = self.total_debits(currency) - self.total_credits(currency)
            if difference:
                net[currency] = difference
        return dict(net)

    def is_balanced(self) -> bool:
        return not self.imbalance()

    def assert_balanced(self) -> None:
        imbalance = self.imbalance()
        if imbalance:
            raise Refused(f"the ledger is out of balance: {imbalance}")

    def entry_count(self) -> int:
        return len(self.entries)
