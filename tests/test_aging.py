from __future__ import annotations

import datetime

import pytest

from mint.aging import AgingItem, age
from mint.errors import CurrencyMismatch, Refused
from mint.money import Money

AS_OF = datetime.date(2026, 4, 1)


def _item(item_id, amount, due_day):
    return AgingItem(item_id, Money.of(amount, "USD"), due_day)


class TestBuckets:
    def test_a_not_yet_due_item_is_current(self):
        report = age([_item("A", 100, datetime.date(2026, 4, 15))], AS_OF, "USD")
        assert report.bucket_of("A") == "current"

    def test_exactly_thirty_days_is_the_first_bucket(self):
        report = age([_item("A", 100, datetime.date(2026, 3, 2))], AS_OF, "USD")
        assert report.bucket_of("A") == "1-30"

    def test_thirty_one_days_crosses_into_the_next(self):
        report = age([_item("A", 100, datetime.date(2026, 3, 1))], AS_OF, "USD")
        assert report.bucket_of("A") == "31-60"

    def test_past_ninety_is_the_open_ended_bucket(self):
        report = age([_item("A", 100, datetime.date(2025, 12, 1))], AS_OF, "USD")
        assert report.bucket_of("A") == ">90"


class TestTotals:
    def test_totals_sum_per_bucket(self):
        report = age(
            [
                _item("A", 100, datetime.date(2026, 3, 2)),
                _item("B", 50, datetime.date(2026, 3, 20)),
                _item("C", 25, datetime.date(2026, 5, 1)),
            ],
            AS_OF,
            "USD",
        )
        assert report.bucket_total("1-30") == Money.of(150, "USD")
        assert report.bucket_total("current") == Money.of(25, "USD")
        assert report.total() == Money.of(175, "USD")


class TestRefusals:
    def test_a_mixed_currency_run_is_refused(self):
        with pytest.raises(CurrencyMismatch):
            age([AgingItem("A", Money.of(1, "EUR"), AS_OF)], AS_OF, "USD")

    def test_disordered_edges_are_refused(self):
        with pytest.raises(Refused):
            age([_item("A", 1, AS_OF)], AS_OF, "USD", edges=(60, 30))

    def test_an_unknown_bucket_is_refused(self):
        report = age([_item("A", 1, AS_OF)], AS_OF, "USD")
        with pytest.raises(Refused):
            report.bucket_total("nonsense")
