"""Assay: closing a period moves exactly the profit and leaves the books balanced.

The close is the entry with the widest blast radius in a ledger: it
touches every income and expense account at once and moves the
residue into equity, so an error there misstates both the year just
ended and the one beginning. Three things must be true afterward
and this assay measures all three. Every temporary account is at
zero, so the new period starts from scratch. Retained earnings has
moved by exactly the net income the income statement reported, no
more and no less, which ties the two statements together through
the close rather than by assertion. And the ledger is still
balanced, which it must be since the close is a single balanced
entry, but which is worth confirming because the close builds its
entry programmatically from whatever accounts happen to exist and
that is precisely the kind of construction that goes wrong quietly.
The assay closes a period with an awkward profit rather than a
round one, since a close that only works on round numbers is a
close that has not been tested.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.assays.framework import Finding, assay
from mint.book import Book
from mint.close import close_period, net_income
from mint.incomestatement import income_statement
from mint.money import Money

START = datetime.date(2026, 1, 1)
END = datetime.date(2026, 12, 31)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("3000", "Capital", AccountType.EQUITY, "USD")
    book.open("3900", "Retained", AccountType.EQUITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("4100", "Services", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.open("5100", "Supplies", AccountType.EXPENSE, "USD")
    day = datetime.date(2026, 6, 1)
    book.post(
        book.transaction(day).debit("1000", Money.of(5000, "USD")).credit(
            "3000", Money.of(5000, "USD")
        )
    )
    for account, amount in (("4000", "7351.29"), ("4100", "2648.77")):
        book.post(
            book.transaction(day).debit("1000", Money.of(amount, "USD")).credit(
                account, Money.of(amount, "USD")
            )
        )
    for account, amount in (("5000", "3199.99"), ("5100", "1450.03")):
        book.post(
            book.transaction(day).debit(account, Money.of(amount, "USD")).credit(
                "1000", Money.of(amount, "USD")
            )
        )
    return book


@assay("closing", "does the period close move exactly the profit and stay balanced")
def _probe() -> list[Finding]:
    book = _book()
    findings: list[Finding] = []

    expected = net_income(book, "USD")
    statement = income_statement(book.ledger, "USD", START, END)
    findings.append(
        Finding(
            "net income agrees with the statement",
            expected.units,
            statement.net_income().units,
        )
    )
    findings.append(Finding("net income measured", expected.units, 535004))

    result = close_period(book, "3900", END)
    findings.append(Finding("the close returned the net income", result.units, expected.units))

    temporaries = ["4000", "4100", "5000", "5100"]
    leftovers = sum(abs(book.balance(code).units) for code in temporaries)
    findings.append(Finding("temporary accounts left holding", leftovers, 0))

    findings.append(
        Finding("retained earnings after close", book.balance("3900").units, 535004)
    )
    findings.append(Finding("ledger imbalance after close", book.ledger.imbalance(), {}))
    return findings
