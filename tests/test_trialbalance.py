from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.money import Money
from mint.trialbalance import trial_balance

DAY = datetime.date(2026, 1, 1)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("3000", "Capital", AccountType.EQUITY, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.open("5000", "Rent", AccountType.EXPENSE, "USD")
    book.open("1500", "Cash EUR", AccountType.ASSET, "EUR")
    book.post(
        book.transaction(DAY).debit("1000", Money.of(1000, "USD")).credit(
            "3000", Money.of(1000, "USD")
        )
    )
    book.post(
        book.transaction(DAY).debit("1000", Money.of(200, "USD")).credit(
            "4000", Money.of(200, "USD")
        )
    )
    book.post(
        book.transaction(DAY).debit("5000", Money.of(150, "USD")).credit(
            "1000", Money.of(150, "USD")
        )
    )
    return book


class TestTrialBalance:
    def test_the_columns_are_equal(self):
        tb = trial_balance(_book().ledger, "USD")
        assert tb.balances()
        assert tb.difference() == 0

    def test_cash_is_a_net_debit(self):
        tb = trial_balance(_book().ledger, "USD")
        cash = next(line for line in tb.lines if line.code == "1000")
        assert cash.debit == 105000
        assert cash.credit == 0

    def test_sales_is_a_net_credit(self):
        tb = trial_balance(_book().ledger, "USD")
        sales = next(line for line in tb.lines if line.code == "4000")
        assert sales.credit == 20000
        assert sales.debit == 0

    def test_zero_accounts_are_hidden_but_counted(self):
        tb = trial_balance(_book().ledger, "USD")
        assert all(line.code != "1500" for line in tb.lines)

    def test_only_the_named_currency_appears(self):
        tb = trial_balance(_book().ledger, "USD")
        assert tb.currency == "USD"
        assert all(line.code != "1500" for line in tb.lines)
