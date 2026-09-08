"""Assay: a full payment lifecycle leaves the books balanced and settled.

The gateway turns payment events into double entries, and the claim
worth measuring is that no sequence of them ever breaks the books.
This assay runs a realistic lifecycle, several captures, a fee, a
partial refund, and a payout, and checks three things: the ledger
is still globally balanced, the clearing account is emptied to the
bank by the payout so no money is stranded in transit, and the net
revenue equals gross captures less refunds. Each of those is a
number the gateway must produce by construction, but constructing
the entries by hand is exactly where a sign or an account role gets
transposed, so measuring the composed result is what would catch a
transposition that each entry alone looks fine under.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.assays.framework import Finding, assay
from mint.book import Book
from mint.gateway import Gateway, GatewayAccounts
from mint.idempotency import IdempotencyStore
from mint.money import Money

DAY = datetime.date(2026, 1, 1)


def _gateway() -> Gateway:
    book = Book()
    book.open("1000", "Clearing", AccountType.ASSET, "USD")
    book.open("1100", "Bank", AccountType.ASSET, "USD")
    book.open("4000", "Revenue", AccountType.INCOME, "USD")
    book.open("4900", "Refunds", AccountType.INCOME, "USD")
    book.open("5000", "Fees", AccountType.EXPENSE, "USD")
    accounts = GatewayAccounts("1000", "1100", "4000", "4900", "5000")
    return Gateway(book, accounts, IdempotencyStore())


@assay("lifecycle", "does a full payment lifecycle keep the books balanced and settled")
def _probe() -> list[Finding]:
    gw = _gateway()
    charge_one = gw.capture(Money.of("120.00", "USD"), DAY, "c1")
    gw.capture(Money.of("80.00", "USD"), DAY, "c2")
    gw.charge_fee(Money.of("5.80", "USD"), DAY)
    gw.refund(charge_one, Money.of("20.00", "USD"), DAY, "one item back")
    gw.payout(DAY)

    findings: list[Finding] = []
    findings.append(Finding("book imbalance", gw.book.ledger.imbalance(), {}))
    findings.append(Finding("clearing emptied by payout", gw.book.balance("1000").units, 0))
    findings.append(Finding("net revenue after refund", gw.net_revenue().units, 18000))
    findings.append(
        Finding("bank received the net payout", gw.book.balance("1100").units, 17420)
    )
    return findings
