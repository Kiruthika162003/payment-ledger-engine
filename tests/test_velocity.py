from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.velocity import VelocityCounter, VelocityLimit

BASE = datetime.datetime(2026, 1, 1, 10, 0, 0)
HOUR = datetime.timedelta(hours=1)


def _counter() -> VelocityCounter:
    return VelocityCounter(
        currency="USD",
        limits=[
            VelocityLimit(window=HOUR, max_count=3),
            VelocityLimit(window=HOUR, max_amount=Money.of(1000, "USD")),
        ],
    )


class TestCountLimit:
    def test_attempts_under_the_cap_pass(self):
        counter = _counter()
        for offset in range(3):
            breach = counter.check_and_record(
                Money.of(10, "USD"), BASE + datetime.timedelta(minutes=offset)
            )
            assert breach is None

    def test_the_fourth_attempt_breaches(self):
        counter = _counter()
        for offset in range(3):
            counter.check_and_record(
                Money.of(10, "USD"), BASE + datetime.timedelta(minutes=offset)
            )
        breach = counter.check_and_record(
            Money.of(10, "USD"), BASE + datetime.timedelta(minutes=4)
        )
        assert "unlike its owner" in breach


class TestAmountLimit:
    def test_a_large_charge_breaches_the_amount_cap(self):
        counter = _counter()
        breach = counter.check_and_record(Money.of(1500, "USD"), BASE)
        assert breach is not None
        assert "1,000" in breach or "1000" in breach

    def test_amounts_accumulate_toward_the_cap(self):
        counter = _counter()
        counter.check_and_record(Money.of(600, "USD"), BASE)
        breach = counter.check_and_record(
            Money.of(600, "USD"), BASE + datetime.timedelta(minutes=1)
        )
        assert breach is not None


class TestSlidingWindow:
    def test_the_window_slides_rather_than_resetting_on_the_hour(self):
        counter = _counter()
        for offset in (0, 1, 2):
            counter.check_and_record(
                Money.of(10, "USD"), BASE + datetime.timedelta(minutes=59 + offset)
            )
        # Two minutes later the earlier attempts are still inside the window.
        breach = counter.check_and_record(
            Money.of(10, "USD"), BASE + datetime.timedelta(minutes=62)
        )
        assert breach is not None

    def test_attempts_age_out_of_the_window(self):
        counter = _counter()
        for offset in range(3):
            counter.check_and_record(
                Money.of(10, "USD"), BASE + datetime.timedelta(minutes=offset)
            )
        later = BASE + datetime.timedelta(hours=2)
        assert counter.check_and_record(Money.of(10, "USD"), later) is None


class TestDeclinedAttempts:
    def test_a_declined_attempt_still_counts(self):
        counter = _counter()
        counter.check_and_record(Money.of(1500, "USD"), BASE)
        assert counter.count_in(BASE, HOUR) == 1
        assert counter.accepted_count() == 0


class TestConstruction:
    def test_a_limit_that_caps_nothing_is_refused(self):
        with pytest.raises(Refused) as caught:
            VelocityLimit(window=HOUR)
        assert "permits everything" in str(caught.value)

    def test_a_zero_window_is_refused(self):
        with pytest.raises(Refused):
            VelocityLimit(window=datetime.timedelta(0), max_count=1)

    def test_a_wrong_currency_check_is_refused(self):
        with pytest.raises(Refused):
            _counter().would_breach(Money.of(10, "EUR"), BASE)
