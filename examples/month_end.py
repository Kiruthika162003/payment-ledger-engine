"""A month-end close: accruals, deferrals, statements, and the closing entry.

This example runs a services business through the work a controller
actually does at month end. Revenue is billed and some of it is
collected up front and therefore deferred; an expense is incurred
whose invoice has not arrived and is therefore accrued; the
statements are drawn; and the period is closed into retained
earnings. It composes the recognition modules with the reporting
ones and ends by confirming the books balance, which is the point
of the whole exercise.
"""

from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.balancesheet import balance_sheet
from mint.book import Book
from mint.close import close_period
from mint.deferral import monthly_schedule
from mint.incomestatement import income_statement
from mint.money import Money
from mint.trialbalance import trial_balance

START = datetime.date(2026, 3, 1)
END = datetime.date(2026, 3, 31)


def _dollars(money: Money) -> str:
    return money.format(with_symbol=False)


def run() -> list[str]:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("1200", "Receivable", AccountType.ASSET, "USD")
    book.open("2100", "Deferred Revenue", AccountType.LIABILITY, "USD")
    book.open("2200", "Accrued Expenses", AccountType.LIABILITY, "USD")
    book.open("3900", "Retained Earnings", AccountType.EQUITY, "USD")
    book.open("4000", "Services Revenue", AccountType.INCOME, "USD")
    book.open("5000", "Contractors", AccountType.EXPENSE, "USD")

    lines = ["Month end, March 2026"]

    book.post(
        book.transaction(datetime.date(2026, 3, 5), "invoice a client")
        .debit("1200", Money.of(9000, "USD"))
        .credit("4000", Money.of(9000, "USD"))
    )
    lines.append(f"Billed on account: {_dollars(book.balance('1200'))}")

    book.post(
        book.transaction(datetime.date(2026, 3, 10), "annual plan collected")
        .debit("1000", Money.of(1200, "USD"))
        .credit("2100", Money.of(1200, "USD"))
    )
    lines.append(f"Collected in advance, deferred: {_dollars(book.balance('2100'))}")

    plan = monthly_schedule(Money.of(1200, "USD"), START, 12)
    earned = plan.rows[0]
    book.post(
        book.transaction(END, "recognize one month of the annual plan")
        .debit("2100", Money.from_minor(earned.recognized, "USD"))
        .credit("4000", Money.from_minor(earned.recognized, "USD"))
    )
    recognized = Money.from_minor(earned.recognized, "USD")
    lines.append(f"Recognized this month: {_dollars(recognized)}")
    lines.append(f"Still deferred: {_dollars(book.balance('2100'))}")

    book.post(
        book.transaction(END, "accrue contractor invoice not yet received")
        .debit("5000", Money.of("2450.75", "USD"))
        .credit("2200", Money.of("2450.75", "USD"))
    )
    lines.append(f"Accrued expense: {_dollars(book.balance('2200'))}")

    statement = income_statement(book.ledger, "USD", START, END)
    revenue = Money.from_minor(statement.revenue.total, "USD")
    expenses = Money.from_minor(statement.expense.total, "USD")
    lines.append(f"Revenue for March: {_dollars(revenue)}")
    lines.append(f"Expenses for March: {_dollars(expenses)}")
    lines.append(f"Net income: {_dollars(statement.net_income())}")

    trial = trial_balance(book.ledger, "USD")
    lines.append(f"Trial balance columns equal: {trial.balances()}")

    sheet = balance_sheet(book.ledger, "USD", END)
    lines.append(f"Balance sheet balances: {sheet.balances()}")

    result = close_period(book, "3900", END)
    lines.append(f"Closed; retained earnings: {_dollars(result)}")
    lines.append(f"Revenue after close: {_dollars(book.balance('4000'))}")
    lines.append(f"Books balanced: {book.is_balanced()}")
    return lines


def main() -> None:
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
