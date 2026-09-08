from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, allocate, round_fraction, round_money, scale, split


class TestRoundingModes:
    def test_half_even_rounds_a_half_to_the_even_neighbor(self):
        assert round_fraction(Fraction(5, 2), Rounding.HALF_EVEN) == 2
        assert round_fraction(Fraction(7, 2), Rounding.HALF_EVEN) == 4

    def test_half_up_always_rounds_a_half_away_from_zero(self):
        assert round_fraction(Fraction(5, 2), Rounding.HALF_UP) == 3
        assert round_fraction(Fraction(-5, 2), Rounding.HALF_UP) == -3

    def test_floor_and_ceiling_are_directional(self):
        assert round_fraction(Fraction(-1, 3), Rounding.FLOOR) == -1
        assert round_fraction(Fraction(1, 3), Rounding.CEILING) == 1

    def test_down_truncates_toward_zero(self):
        assert round_fraction(Fraction(-7, 3), Rounding.DOWN) == -2

    def test_up_rounds_away_from_zero(self):
        assert round_fraction(Fraction(-7, 3), Rounding.UP) == -3

    def test_a_non_half_remainder_ignores_the_tie_rule(self):
        assert round_fraction(Fraction(7, 3), Rounding.HALF_EVEN) == 2


class TestScale:
    def test_scaling_rounds_the_fraction_to_money(self):
        assert scale(Money.of(1, "USD"), Fraction(1, 3)) == Money.from_minor(33, "USD")

    def test_round_money_wraps_a_fraction(self):
        assert round_money(Fraction(100, 3), "USD") == Money.from_minor(33, "USD")


class TestAllocation:
    def test_a_dollar_in_three_conserves_every_cent(self):
        parts = split(Money.of(1, "USD"), 3)
        assert [p.units for p in parts] == [34, 33, 33]
        assert sum(p.units for p in parts) == 100

    def test_a_weighted_split_follows_the_weights(self):
        parts = allocate(Money.of(1, "USD"), [1, 1, 2])
        assert [p.units for p in parts] == [25, 25, 50]

    def test_the_leftover_goes_to_the_largest_remainder(self):
        # 100 split 1:1:1 gives exact thirds of 33.33; the two extra
        # cents go to the two shares tied highest, earliest index first.
        parts = allocate(Money.of(1, "USD"), [1, 1, 1])
        assert [p.units for p in parts] == [34, 33, 33]

    def test_a_negative_total_mirrors_the_positive_split(self):
        parts = split(Money.of("-1.00", "USD"), 3)
        assert [p.units for p in parts] == [-34, -33, -33]
        assert sum(p.units for p in parts) == -100

    def test_zero_shares_are_refused(self):
        with pytest.raises(Refused) as caught:
            allocate(Money.of(1, "USD"), [0, 0])
        assert "sum to zero" in str(caught.value)

    def test_a_negative_share_is_refused(self):
        with pytest.raises(Refused):
            allocate(Money.of(1, "USD"), [3, -1])

    def test_an_empty_allocation_is_refused(self):
        with pytest.raises(Refused):
            allocate(Money.of(1, "USD"), [])
