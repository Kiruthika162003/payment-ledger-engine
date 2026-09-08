from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.money import Money
from mint.statement import statement

JAN = datetime.date(2026, 1, 15)
FEB = datetime.date(2026, 2, 15)
MAR = datetime.date(2026, 3, 15)
FEB_START = datetime.date(2026, 2, 1)
FEB_END = datetime.date(2026, 2, 28)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.post(
        book.transaction(JAN, "opening sale").debit("1000", Money.of(100, "USD")).credit(
            "4000", Money.of(100, "USD")
        )
    )
    book.post(
        book.transaction(FEB, "february sale").debit("1000", Money.of(50, "USD")).credit(
            "4000", Money.of(50, "USD")
        )
    )
    book.post(
        book.transaction(FEB, "february rent").debit("5000", Money.of(30, "USD")).credit(
            "1000", Money.of(30, "USD")
        )
    )
    return book


class TestStatement:
    def test_opening_reflects_prior_movements(self):
        stmt = statement(_book().ledger, "1000", FEB_START, FEB_END)
        assert stmt.opening == Money.of(100, "USD")

    def test_closing_equals_opening_plus_movement(self):
        stmt = statement(_book().ledger, "1000", FEB_START, FEB_END)
        assert stmt.closing == Money.of(120, "USD")
        assert stmt.movement() == Money.of(20, "USD")

    def test_lines_cover_only_the_period(self):
        stmt = statement(_book().ledger, "1000", FEB_START, FEB_END)
        assert stmt.line_count() == 2

    def test_the_running_balance_tracks_each_line(self):
        stmt = statement(_book().ledger, "1000", JAN, MAR)
        assert [line.balance for line in stmt.lines] == [10000, 15000, 12000]

    def test_closing_matches_the_independent_balance(self):
        book = _book()
        stmt = statement(book.ledger, "1000", JAN, MAR)
        assert stmt.closing == book.balance("1000")
