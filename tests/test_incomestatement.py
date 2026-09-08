from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.incomestatement import income_statement
from mint.money import Money

JAN = datetime.date(2026, 1, 10)
FEB = datetime.date(2026, 2, 10)
Q1_START = datetime.date(2026, 1, 1)
Q1_END = datetime.date(2026, 3, 31)
JAN_END = datetime.date(2026, 1, 31)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.post(
        book.transaction(JAN).debit("1000", Money.of(300, "USD")).credit(
            "4000", Money.of(300, "USD")
        )
    )
    book.post(
        book.transaction(FEB).debit("1000", Money.of(200, "USD")).credit(
            "4000", Money.of(200, "USD")
        )
    )
    book.post(
        book.transaction(FEB).debit("5000", Money.of(120, "USD")).credit(
            "1000", Money.of(120, "USD")
        )
    )
    return book


class TestIncomeStatement:
    def test_net_income_over_the_quarter(self):
        stmt = income_statement(_book().ledger, "USD", Q1_START, Q1_END)
        assert stmt.revenue.total == 50000
        assert stmt.expense.total == 12000
        assert stmt.net_income() == Money.of(380, "USD")
        assert stmt.is_profit()

    def test_a_narrower_window_is_a_flow_not_a_level(self):
        stmt = income_statement(_book().ledger, "USD", Q1_START, JAN_END)
        assert stmt.revenue.total == 30000
        assert stmt.expense.total == 0
        assert stmt.net_income() == Money.of(300, "USD")

    def test_the_margin_ratio(self):
        stmt = income_statement(_book().ledger, "USD", Q1_START, Q1_END)
        assert abs(stmt.margin_ratio() - 0.76) < 1e-9

    def test_no_revenue_gives_a_zero_margin(self):
        book = Book()
        book.open("1000", "Cash", AccountType.ASSET, "USD")
        book.open("5000", "Rent", AccountType.EXPENSE, "USD")
        book.open("3000", "Capital", AccountType.EQUITY, "USD")
        book.post(
            book.transaction(JAN).debit("1000", Money.of(10, "USD")).credit(
                "3000", Money.of(10, "USD")
            )
        )
        book.post(
            book.transaction(JAN).debit("5000", Money.of(5, "USD")).credit(
                "1000", Money.of(5, "USD")
            )
        )
        stmt = income_statement(book.ledger, "USD", Q1_START, Q1_END)
        assert stmt.margin_ratio() == 0.0
