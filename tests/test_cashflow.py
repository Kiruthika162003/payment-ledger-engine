from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.cashflow import cash_flow
from mint.money import Money

JAN = datetime.date(2026, 1, 5)
FEB = datetime.date(2026, 2, 5)
START = datetime.date(2026, 1, 1)
END = datetime.date(2026, 3, 1)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("1100", "Savings", AccountType.ASSET, "USD")
    book.open("2000", "Loan", AccountType.LIABILITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.post(
        book.transaction(JAN).debit("1000", Money.of(500, "USD")).credit(
            "2000", Money.of(500, "USD")
        )
    )
    book.post(
        book.transaction(JAN).debit("1000", Money.of(300, "USD")).credit(
            "4000", Money.of(300, "USD")
        )
    )
    book.post(
        book.transaction(FEB).debit("5000", Money.of(120, "USD")).credit(
            "1000", Money.of(120, "USD")
        )
    )
    book.post(
        book.transaction(FEB).debit("1100", Money.of(200, "USD")).credit(
            "1000", Money.of(200, "USD")
        )
    )
    return book


class TestCashFlow:
    def test_the_internal_sweep_is_dropped(self):
        cf = cash_flow(_book().ledger, ["1000", "1100"], "USD", START, END)
        assert all(code != "1100" for code, _ in cf.uses)
        assert all(code != "1100" for code, _ in cf.sources)

    def test_sources_and_uses_are_attributed(self):
        cf = cash_flow(_book().ledger, ["1000"], "USD", START, END)
        sources = dict(cf.sources)
        uses = dict(cf.uses)
        assert sources["2000"] == 50000
        assert sources["4000"] == 30000
        assert uses["5000"] == 12000

    def test_the_sweep_shows_as_a_use_of_the_checking_cash(self):
        cf = cash_flow(_book().ledger, ["1000"], "USD", START, END)
        assert dict(cf.uses)["1100"] == 20000

    def test_net_change_reconciles_to_closing_minus_opening(self):
        cf = cash_flow(_book().ledger, ["1000", "1100"], "USD", START, END)
        assert cf.reconciles()
        assert cf.net_change() == Money.of(680, "USD")
