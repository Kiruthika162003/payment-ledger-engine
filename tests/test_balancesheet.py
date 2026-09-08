from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.balancesheet import balance_sheet
from mint.book import Book
from mint.close import close_period
from mint.money import Money

DAY = datetime.date(2026, 5, 1)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("2000", "Loan", AccountType.LIABILITY, "USD")
    book.open("3000", "Capital", AccountType.EQUITY, "USD")
    book.open("3900", "Retained", AccountType.EQUITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.post(
        book.transaction(DAY).debit("1000", Money.of(1000, "USD")).credit(
            "3000", Money.of(1000, "USD")
        )
    )
    book.post(
        book.transaction(DAY).debit("1000", Money.of(500, "USD")).credit(
            "2000", Money.of(500, "USD")
        )
    )
    book.post(
        book.transaction(DAY).debit("1000", Money.of(200, "USD")).credit(
            "4000", Money.of(200, "USD")
        )
    )
    book.post(
        book.transaction(DAY).debit("5000", Money.of(80, "USD")).credit(
            "1000", Money.of(80, "USD")
        )
    )
    return book


class TestBalanceSheet:
    def test_it_balances_before_close(self):
        sheet = balance_sheet(_book().ledger, "USD", DAY)
        assert sheet.balances()
        assert sheet.difference() == 0

    def test_current_earnings_appear_in_equity(self):
        sheet = balance_sheet(_book().ledger, "USD", DAY)
        earnings = next(row for row in sheet.equity.lines if row[1] == "Current earnings")
        assert earnings[2] == 12000

    def test_total_assets_match_the_other_side(self):
        sheet = balance_sheet(_book().ledger, "USD", DAY)
        assert sheet.total_assets() == sheet.total_liabilities_and_equity()
        assert sheet.total_assets() == Money.of("1620.00", "USD")

    def test_it_balances_after_close_too(self):
        book = _book()
        close_period(book, "3900", DAY)
        sheet = balance_sheet(book.ledger, "USD", DAY)
        assert sheet.balances()
        assert all(row[1] != "Current earnings" for row in sheet.equity.lines)
