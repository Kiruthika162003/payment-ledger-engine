from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.lease import initial_liability, schedule
from mint.money import Money

RATE = Fraction(1, 100)


class TestInitialLiability:
    def test_it_is_the_present_value_of_the_payments(self):
        liability = initial_liability(Money.of(100, "USD"), RATE, 12)
        assert liability == Money.from_minor(112551, "USD")

    def test_paying_in_advance_raises_the_liability(self):
        arrears = initial_liability(Money.of(100, "USD"), RATE, 12)
        advance = initial_liability(Money.of(100, "USD"), RATE, 12, in_advance=True)
        assert advance > arrears


class TestSchedule:
    def test_the_liability_closes_exactly_on_zero(self):
        result = schedule(Money.of(100, "USD"), RATE, 12)
        assert result.final_liability() == 0

    def test_the_asset_amortizes_to_zero(self):
        result = schedule(Money.of(100, "USD"), RATE, 12)
        assert result.final_asset() == 0
        assert result.closes()

    def test_interest_falls_as_the_liability_shrinks(self):
        result = schedule(Money.of(100, "USD"), RATE, 12)
        assert result.rows[0].interest > result.rows[-2].interest

    def test_amortization_is_straight_line(self):
        result = schedule(Money.of(100, "USD"), RATE, 12)
        amounts = {row.amortization for row in result.rows}
        # Straight line up to the cent the allocation distributes.
        assert len(amounts) <= 2

    def test_total_payments_exceed_the_liability_by_the_interest(self):
        result = schedule(Money.of(100, "USD"), RATE, 12)
        assert (
            result.total_payments() - result.initial_liability
            == result.total_interest()
        )


class TestAdvance:
    def test_an_advance_lease_also_closes(self):
        result = schedule(Money.of(100, "USD"), RATE, 12, in_advance=True)
        assert result.closes()

    def test_an_advance_lease_pays_less_interest(self):
        arrears = schedule(Money.of(100, "USD"), RATE, 12)
        advance = schedule(Money.of(100, "USD"), RATE, 12, in_advance=True)
        assert advance.total_interest() < arrears.total_interest()


class TestZeroRate:
    def test_an_interest_free_lease_is_just_the_payments(self):
        result = schedule(Money.of(100, "USD"), Fraction(0), 12)
        assert result.initial_liability == Money.of(1200, "USD")
        assert result.total_interest().is_zero()
        assert result.closes()


class TestRefusals:
    def test_zero_periods_is_refused(self):
        with pytest.raises(Refused):
            schedule(Money.of(100, "USD"), RATE, 0)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            schedule(Money.of(100, "USD"), Fraction(-1, 100), 12)
