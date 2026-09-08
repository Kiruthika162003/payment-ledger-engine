from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.chart import Chart
from mint.entry import entry
from mint.errors import CurrencyMismatch, UnknownAccount
from mint.ledger import Ledger
from mint.money import Money
from mint.posting import credit, debit

DAY = datetime.date(2026, 1, 1)


def _ledger() -> Ledger:
    chart = Chart()
    chart.add("1000", "Cash", AccountType.ASSET, "USD")
    chart.add("4000", "Sales", AccountType.INCOME, "USD")
    chart.add("5000", "Rent", AccountType.EXPENSE, "USD")
    chart.add("1500", "Cash EUR", AccountType.ASSET, "EUR")
    return Ledger(chart)


class TestPosting:
    def test_a_sale_moves_cash_and_revenue(self):
        ledger = _ledger()
        ledger.post(
            entry(
                [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(10, "USD"))],
                DAY,
            )
        )
        assert ledger.balance("1000") == Money.of(10, "USD")
        assert ledger.balance("4000") == Money.of(10, "USD")

    def test_posting_to_an_unknown_account_is_refused(self):
        ledger = _ledger()
        with pytest.raises(UnknownAccount):
            ledger.post(
                entry(
                    [
                        debit("9999", Money.of(10, "USD")),
                        credit("4000", Money.of(10, "USD")),
                    ],
                    DAY,
                )
            )

    def test_the_wrong_currency_for_an_account_is_refused(self):
        ledger = _ledger()
        with pytest.raises(CurrencyMismatch) as caught:
            ledger.post(
                entry(
                    [
                        debit("1000", Money.of(10, "EUR")),
                        credit("1500", Money.of(10, "EUR")),
                    ],
                    DAY,
                )
            )
        assert "separate account" in str(caught.value)


class TestBalances:
    def test_balances_are_folded_from_the_entries(self):
        ledger = _ledger()
        for _ in range(3):
            ledger.post(
                entry(
                    [
                        debit("1000", Money.of(10, "USD")),
                        credit("4000", Money.of(10, "USD")),
                    ],
                    DAY,
                )
            )
        assert ledger.balance("1000") == Money.of(30, "USD")
        assert ledger.raw_debits("1000") == 3000
        assert ledger.raw_credits("1000") == 0

    def test_an_expense_debit_grows_positive(self):
        ledger = _ledger()
        ledger.post(
            entry(
                [debit("5000", Money.of(4, "USD")), credit("1000", Money.of(4, "USD"))],
                DAY,
            )
        )
        assert ledger.balance("5000") == Money.of(4, "USD")
        assert ledger.balance("1000") == Money.of("-4.00", "USD")

    def test_nonzero_balances_hide_the_settled_accounts(self):
        ledger = _ledger()
        ledger.post(
            entry(
                [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(10, "USD"))],
                DAY,
            )
        )
        assert set(ledger.nonzero_balances()) == {"1000", "4000"}


class TestGlobalBalance:
    def test_the_whole_ledger_stays_balanced(self):
        ledger = _ledger()
        ledger.post(
            entry(
                [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(10, "USD"))],
                DAY,
            )
        )
        ledger.post(
            entry(
                [debit("5000", Money.of(3, "USD")), credit("1000", Money.of(3, "USD"))],
                DAY,
            )
        )
        assert ledger.is_balanced()
        assert ledger.total_debits("USD") == ledger.total_credits("USD")

    def test_the_entry_count_tracks_postings(self):
        ledger = _ledger()
        ledger.post(
            entry(
                [debit("1000", Money.of(1, "USD")), credit("4000", Money.of(1, "USD"))],
                DAY,
            )
        )
        assert ledger.entry_count() == 1
