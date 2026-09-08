"""Assay: the ledger balances globally and the accounting equation holds.

Two claims sit at the center of double entry, and this assay
measures both after a run of ordinary transactions rather than a
single contrived one. The first is the trial balance: the sum of
every debit posted equals the sum of every credit posted, which
follows from each entry balancing but is worth confirming against
the real posting path. The second is the accounting equation in
its signed form, that the total of the debit-normal accounts,
assets and expenses, equals the total of the credit-normal
accounts, liabilities and equity and income. That equality is not
an accident of the example; it is the trial balance rearranged, so
if the ledger ever posted a leg to the wrong side the two totals
would part and this assay would show the gap in cents.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.assays.framework import Finding, assay
from mint.book import Book
from mint.money import Money

DAY = datetime.date(2026, 1, 1)


def _run() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("1200", "Receivable", AccountType.ASSET, "USD")
    book.open("2000", "Payable", AccountType.LIABILITY, "USD")
    book.open("3000", "Capital", AccountType.EQUITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")

    book.post(
        book.transaction(DAY, "owner invests")
        .debit("1000", Money.of(1000, "USD"))
        .credit("3000", Money.of(1000, "USD"))
    )
    for _ in range(5):
        book.post(
            book.transaction(DAY, "cash sale")
            .debit("1000", Money.of("49.99", "USD"))
            .credit("4000", Money.of("49.99", "USD"))
        )
    book.post(
        book.transaction(DAY, "sale on credit")
        .debit("1200", Money.of("120.50", "USD"))
        .credit("4000", Money.of("120.50", "USD"))
    )
    book.post(
        book.transaction(DAY, "rent on account")
        .debit("5000", Money.of(300, "USD"))
        .credit("2000", Money.of(300, "USD"))
    )
    return book


def _signed_total(book: Book, account_type: AccountType) -> int:
    return sum(
        book.ledger.balance_units(account.code)
        for account in book.chart.of_type(account_type)
    )


@assay("balance", "does the ledger balance globally and satisfy the accounting equation")
def _probe() -> list[Finding]:
    book = _run()
    findings: list[Finding] = []

    findings.append(Finding("global imbalance in cents", book.ledger.imbalance(), {}))

    debit_normal = _signed_total(book, AccountType.ASSET) + _signed_total(
        book, AccountType.EXPENSE
    )
    credit_normal = (
        _signed_total(book, AccountType.LIABILITY)
        + _signed_total(book, AccountType.EQUITY)
        + _signed_total(book, AccountType.INCOME)
    )
    findings.append(
        Finding("assets plus expenses minus the rest", debit_normal - credit_normal, 0)
    )

    findings.append(
        Finding("trial balance debits versus credits",
                book.ledger.total_debits("USD") - book.ledger.total_credits("USD"), 0)
    )
    return findings
