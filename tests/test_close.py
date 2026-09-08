from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.book import Book
from mint.close import close_period, net_income
from mint.errors import Refused
from mint.money import Money

DAY = datetime.date(2026, 12, 31)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("3000", "Capital", AccountType.EQUITY, "USD")
    book.open("3900", "Retained", AccountType.EQUITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.post(
        book.transaction(DAY).debit("1000", Money.of(800, "USD")).credit(
            "4000", Money.of(800, "USD")
        )
    )
    book.post(
        book.transaction(DAY).debit("5000", Money.of(300, "USD")).credit(
            "1000", Money.of(300, "USD")
        )
    )
    return book


class TestNetIncome:
    def test_net_income_is_revenue_less_expense(self):
        assert net_income(_book(), "USD") == Money.of(500, "USD")


class TestClose:
    def test_close_zeroes_the_temporary_accounts(self):
        book = _book()
        close_period(book, "3900", DAY)
        assert book.balance("4000").is_zero()
        assert book.balance("5000").is_zero()

    def test_retained_earnings_absorbs_the_profit(self):
        book = _book()
        result = close_period(book, "3900", DAY)
        assert result == Money.of(500, "USD")
        assert book.balance("3900") == Money.of(500, "USD")

    def test_a_loss_reduces_retained_earnings(self):
        book = Book()
        book.open("1000", "Cash", AccountType.ASSET, "USD")
        book.open("3900", "Retained", AccountType.EQUITY, "USD")
        book.open("4000", "Sales", AccountType.INCOME, "USD")
        book.open("5000", "Rent", AccountType.EXPENSE, "USD")
        book.post(
            book.transaction(DAY).debit("1000", Money.of(100, "USD")).credit(
                "4000", Money.of(100, "USD")
            )
        )
        book.post(
            book.transaction(DAY).debit("5000", Money.of(250, "USD")).credit(
                "1000", Money.of(250, "USD")
            )
        )
        result = close_period(book, "3900", DAY)
        assert result == Money.of("-150.00", "USD")
        assert book.balance("3900") == Money.of("-150.00", "USD")

    def test_the_book_stays_balanced_after_close(self):
        book = _book()
        close_period(book, "3900", DAY)
        assert book.is_balanced()

    def test_closing_a_settled_period_is_refused(self):
        book = _book()
        close_period(book, "3900", DAY)
        with pytest.raises(Refused) as caught:
            close_period(book, "3900", DAY)
        assert "nothing to close" in str(caught.value)
