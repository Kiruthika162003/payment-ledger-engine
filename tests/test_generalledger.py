from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.generalledger import closing_money, general_ledger
from mint.money import Money

JAN = datetime.date(2026, 1, 15)
FEB = datetime.date(2026, 2, 15)
START = datetime.date(2026, 2, 1)
END = datetime.date(2026, 2, 28)
ALL_START = datetime.date(2026, 1, 1)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.open("6000", "Quiet", AccountType.EXPENSE, "USD")
    book.post(
        book.transaction(JAN, "january sale", "S1").debit(
            "1000", Money.of(100, "USD")
        ).credit("4000", Money.of(100, "USD"))
    )
    book.post(
        book.transaction(FEB, "february sale", "S2").debit(
            "1000", Money.of(50, "USD")
        ).credit("4000", Money.of(50, "USD"))
    )
    book.post(
        book.transaction(FEB, "february rent", "R1").debit(
            "5000", Money.of(30, "USD")
        ).credit("1000", Money.of(30, "USD"))
    )
    return book


class TestSections:
    def test_opening_carries_prior_movement(self):
        report = general_ledger(_book().ledger, "USD", START, END)
        assert report.section("1000").opening == 10000

    def test_closing_matches_the_independent_balance(self):
        book = _book()
        report = general_ledger(book.ledger, "USD", START, END)
        assert closing_money(report.section("1000")) == book.balance("1000")

    def test_lines_carry_memo_and_ref(self):
        report = general_ledger(_book().ledger, "USD", START, END)
        line = report.section("5000").lines[0]
        assert line.memo == "february rent"
        assert line.ref == "R1"

    def test_movement_is_closing_less_opening(self):
        report = general_ledger(_book().ledger, "USD", START, END)
        assert report.section("1000").movement() == 2000


class TestQuiet:
    def test_an_account_with_no_movement_is_still_listed(self):
        report = general_ledger(_book().ledger, "USD", START, END)
        assert "6000" in report.quiet_accounts()
        assert report.section("6000").was_quiet()


class TestIdentity:
    def test_debits_equal_credits_across_the_report(self):
        report = general_ledger(_book().ledger, "USD", ALL_START, END)
        assert report.balances()
        assert report.total_debits() == 18000
