"""Assay: the three statements agree with each other, not just with themselves.

A set of financial statements is only trustworthy if it ties out:
the balance sheet balances, the income statement's bottom line is
the same profit the balance sheet carries as unclosed equity, and
the cash flow statement's net change matches the movement in the
cash accounts. Each statement can be internally consistent and
still disagree with the others if a shared assumption drifts, so
this assay builds one scenario and cross-checks all three against
it. The income-statement net income and the balance-sheet current
earnings are computed by different code paths, a period flow versus
an as-of level, and their agreement is the meaningful measurement;
if the two ever part, one of the two statements is lying about the
same business.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.assays.framework import Finding, assay
from mint.balancesheet import balance_sheet
from mint.book import Book
from mint.cashflow import cash_flow
from mint.incomestatement import income_statement
from mint.money import Money

START = datetime.date(2026, 1, 1)
END = datetime.date(2026, 12, 31)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("1200", "Receivable", AccountType.ASSET, "USD")
    book.open("2000", "Loan", AccountType.LIABILITY, "USD")
    book.open("3000", "Capital", AccountType.EQUITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    day = datetime.date(2026, 3, 1)
    book.post(
        book.transaction(day).debit("1000", Money.of(5000, "USD")).credit(
            "3000", Money.of(5000, "USD")
        )
    )
    book.post(
        book.transaction(day).debit("1000", Money.of(2000, "USD")).credit(
            "4000", Money.of(2000, "USD")
        )
    )
    book.post(
        book.transaction(day).debit("1200", Money.of(800, "USD")).credit(
            "4000", Money.of(800, "USD")
        )
    )
    book.post(
        book.transaction(day).debit("5000", Money.of(1100, "USD")).credit(
            "1000", Money.of(1100, "USD")
        )
    )
    book.post(
        book.transaction(day).debit("1000", Money.of(1500, "USD")).credit(
            "2000", Money.of(1500, "USD")
        )
    )
    return book


@assay("statements", "do the balance sheet, income statement, and cash flow tie out")
def _probe() -> list[Finding]:
    book = _book()
    findings: list[Finding] = []

    sheet = balance_sheet(book.ledger, "USD", END)
    findings.append(Finding("balance sheet difference", sheet.difference(), 0))

    stmt = income_statement(book.ledger, "USD", START, END)
    earnings_row = next(
        row for row in sheet.equity.lines if row[1] == "Current earnings"
    )
    findings.append(
        Finding("income statement net equals balance sheet earnings",
                stmt.net_income().units, earnings_row[2])
    )
    findings.append(Finding("net income measured", stmt.net_income().units, 170000))

    cf = cash_flow(book.ledger, ["1000"], "USD", START, END)
    findings.append(Finding("cash flow reconciles", cf.reconciles(), True))
    findings.append(Finding("net cash change measured", cf.net_change().units, 740000))
    return findings
