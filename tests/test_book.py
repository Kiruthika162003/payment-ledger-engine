from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.book import Book
from mint.errors import Refused
from mint.money import Money

DAY = datetime.date(2026, 3, 1)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("1100", "Bank", AccountType.ASSET, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Fees", AccountType.EXPENSE, "USD")
    return book


class TestPosting:
    def test_a_built_transaction_posts(self):
        book = _book()
        book.post(
            book.transaction(DAY, "a sale")
            .debit("1000", Money.of(20, "USD"))
            .credit("4000", Money.of(20, "USD"))
        )
        assert book.balance("1000") == Money.of(20, "USD")

    def test_transfer_moves_between_two_accounts(self):
        book = _book()
        book.post(
            book.transaction(DAY).debit("1000", Money.of(50, "USD")).credit(
                "4000", Money.of(50, "USD")
            )
        )
        book.transfer("1000", "1100", Money.of(30, "USD"), DAY, "sweep")
        assert book.balance("1000") == Money.of(20, "USD")
        assert book.balance("1100") == Money.of(30, "USD")


class TestBalanceAgainst:
    def test_the_last_leg_absorbs_the_remainder(self):
        book = _book()
        txn = (
            book.transaction(DAY, "a sale with a fee")
            .debit("1000", Money.of("9.71", "USD"))
            .debit("5000", Money.of("0.29", "USD"))
            .balance_against("4000", "USD")
        )
        entry = book.post(txn)
        assert entry.is_balanced()
        assert book.balance("4000") == Money.of("10.00", "USD")

    def test_balancing_an_already_balanced_transaction_is_refused(self):
        book = _book()
        txn = (
            book.transaction(DAY)
            .debit("1000", Money.of(10, "USD"))
            .credit("4000", Money.of(10, "USD"))
        )
        with pytest.raises(Refused) as caught:
            txn.balance_against("5000", "USD")
        assert "already balances" in str(caught.value)


class TestFacade:
    def test_the_book_stays_balanced(self):
        book = _book()
        book.post(
            book.transaction(DAY)
            .debit("1000", Money.of(10, "USD"))
            .credit("4000", Money.of(10, "USD"))
        )
        assert book.is_balanced()

    def test_balances_lists_every_account(self):
        book = _book()
        assert set(book.balances()) == {"1000", "1100", "4000", "5000"}
