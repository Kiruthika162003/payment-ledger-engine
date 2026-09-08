"""The book: the facade that ties a chart to a ledger and posts through both.

Most callers do not want to hold a chart and a ledger and keep
them in step by hand; they want to open an account and post a
transaction. The book is that facade. It owns one chart and one
ledger and offers the two verbs a bookkeeper uses, open an account
and record a transaction, delegating balance questions to the
ledger underneath. The transaction builder exists because the most
common mistake in hand-written entries is an off-by-a-cent
imbalance, and a builder that accumulates postings and refuses to
commit until they balance turns that mistake into an immediate,
local error instead of a corrupt entry discovered at close. The
builder also offers to balance an entry automatically against a
named account, which is how real systems post a fee or a rounding
difference: you state the legs you know and let the last leg absorb
whatever is left, and the amount it absorbs is reported so nothing
is balanced silently behind the poster's back.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.accounts import Account, AccountType, Side
from mint.chart import Chart
from mint.entry import Entry, entry
from mint.errors import Refused
from mint.ledger import Ledger
from mint.money import Money
from mint.posting import Posting, credit, debit


@dataclass
class Transaction:
    date: datetime.date
    memo: str = ""
    ref: str = ""
    postings: list[Posting] = field(default_factory=list)

    def debit(self, account: str, amount: Money) -> Transaction:
        self.postings.append(debit(account, amount))
        return self

    def credit(self, account: str, amount: Money) -> Transaction:
        self.postings.append(credit(account, amount))
        return self

    def imbalance(self, currency: str) -> int:
        return sum(
            p.debit_units() - p.credit_units()
            for p in self.postings
            if p.currency == currency
        )

    def balance_against(self, account: str, currency: str) -> Transaction:
        net = self.imbalance(currency)
        if net == 0:
            raise Refused(
                f"the transaction already balances in {currency}; there is "
                f"nothing for {account!r} to absorb"
            )
        side = Side.CREDIT if net > 0 else Side.DEBIT
        self.postings.append(Posting(account, Money.from_minor(abs(net), currency), side))
        return self

    def build(self) -> Entry:
        return entry(self.postings, self.date, self.memo, self.ref)


@dataclass
class Book:
    chart: Chart = field(default_factory=Chart)
    ledger: Ledger = field(init=False)

    def __post_init__(self) -> None:
        self.ledger = Ledger(self.chart)

    def open(
        self,
        code: str,
        name: str,
        account_type: AccountType,
        currency: str,
        parent: str | None = None,
    ) -> Account:
        return self.chart.add(code, name, account_type, currency, parent)

    def transaction(
        self, date: datetime.date, memo: str = "", ref: str = ""
    ) -> Transaction:
        return Transaction(date=date, memo=memo, ref=ref)

    def post(self, transaction: Transaction) -> Entry:
        return self.ledger.post(transaction.build())

    def post_entry(self, built: Entry) -> Entry:
        return self.ledger.post(built)

    def transfer(
        self,
        source: str,
        destination: str,
        amount: Money,
        date: datetime.date,
        memo: str = "",
    ) -> Entry:
        return self.post(
            self.transaction(date, memo)
            .debit(destination, amount)
            .credit(source, amount)
        )

    def balance(self, code: str) -> Money:
        return self.ledger.balance(code)

    def balances(self) -> dict[str, Money]:
        return self.ledger.all_balances()

    def is_balanced(self) -> bool:
        return self.ledger.is_balanced()
