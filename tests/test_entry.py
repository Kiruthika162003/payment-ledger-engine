from __future__ import annotations

import datetime

import pytest

from mint.entry import Entry, entry
from mint.errors import Unbalanced
from mint.money import Money
from mint.posting import credit, debit

DAY = datetime.date(2026, 1, 15)


class TestBalance:
    def test_a_balanced_entry_is_built(self):
        e = entry(
            [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(10, "USD"))],
            DAY,
            memo="a sale",
        )
        assert e.is_balanced()

    def test_an_unbalanced_entry_is_refused(self):
        with pytest.raises(Unbalanced) as caught:
            entry(
                [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(9, "USD"))],
                DAY,
            )
        assert "off by" in str(caught.value)

    def test_an_empty_entry_is_refused(self):
        with pytest.raises(Unbalanced) as caught:
            Entry(postings=(), date=DAY)
        assert "no postings" in str(caught.value)

    def test_a_lone_debit_cannot_balance(self):
        with pytest.raises(Unbalanced):
            entry([debit("1000", Money.of(10, "USD"))], DAY)


class TestMultiCurrency:
    def test_balance_is_checked_per_currency(self):
        e = entry(
            [
                debit("1000", Money.of(10, "USD")),
                credit("4000", Money.of(10, "USD")),
                debit("1500", Money.of(8, "EUR")),
                credit("4500", Money.of(8, "EUR")),
            ],
            DAY,
        )
        assert e.currencies() == ["EUR", "USD"]

    def test_currencies_that_do_not_each_balance_are_refused(self):
        with pytest.raises(Unbalanced):
            entry(
                [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(10, "EUR"))],
                DAY,
            )


class TestQueries:
    def test_totals_by_currency(self):
        e = entry(
            [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(10, "USD"))],
            DAY,
        )
        assert e.debit_total("USD") == 1000
        assert e.credit_total("USD") == 1000

    def test_accounts_and_touches(self):
        e = entry(
            [debit("1000", Money.of(10, "USD")), credit("4000", Money.of(10, "USD"))],
            DAY,
        )
        assert e.accounts() == ["1000", "4000"]
        assert e.touches("1000")
        assert not e.touches("9999")

    def test_postings_for_selects_by_account(self):
        e = entry(
            [
                debit("1000", Money.of(10, "USD")),
                debit("1000", Money.of(5, "USD")),
                credit("4000", Money.of(15, "USD")),
            ],
            DAY,
        )
        assert len(e.postings_for("1000")) == 2
