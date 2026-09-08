from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.subscription import cancellation_credit, prorated_charge, upgrade_charge

START = datetime.date(2026, 1, 1)
END = datetime.date(2026, 1, 31)


class TestProration:
    def test_a_full_period_charges_in_full(self):
        charge = prorated_charge(Money.of(30, "USD"), START, START, END)
        # 30 days remaining of 30, joined on the first day: full price.
        assert charge == Money.of(30, "USD")

    def test_joining_partway_charges_the_remaining_slice(self):
        # 10 days into a 30-day span: 20 of 30 remain, 30.00 * 20/30 = 20.00.
        joined = datetime.date(2026, 1, 11)
        charge = prorated_charge(Money.of(30, "USD"), joined, START, END)
        assert charge == Money.of(20, "USD")

    def test_the_denominator_is_the_real_period_length(self):
        # A 31-day period (Jan 1 to Feb 1), joined with 21 days left.
        feb1 = datetime.date(2026, 2, 1)
        joined = datetime.date(2026, 1, 11)
        charge = prorated_charge(Money.of(31, "USD"), joined, START, feb1)
        assert charge == Money.of(21, "USD")


class TestUpgrade:
    def test_an_upgrade_prorates_the_difference(self):
        joined = datetime.date(2026, 1, 16)
        charge = upgrade_charge(Money.of(30, "USD"), Money.of(60, "USD"), joined, START, END)
        # 15 of 30 days remain, difference 30.00 * 15/30 = 15.00.
        assert charge == Money.of(15, "USD")

    def test_a_non_upgrade_is_refused(self):
        with pytest.raises(Refused):
            upgrade_charge(Money.of(60, "USD"), Money.of(30, "USD"), START, START, END)


class TestRefusals:
    def test_an_effective_date_outside_the_period_is_refused(self):
        with pytest.raises(Refused):
            prorated_charge(Money.of(30, "USD"), datetime.date(2026, 2, 15), START, END)

    def test_cancellation_returns_the_unused_slice(self):
        joined = datetime.date(2026, 1, 11)
        credit = cancellation_credit(Money.of(30, "USD"), joined, START, END)
        assert credit == Money.of(20, "USD")
