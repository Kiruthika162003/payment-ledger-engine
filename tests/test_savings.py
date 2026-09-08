from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.savings import (
    RateTier,
    SavingsProduct,
    TierStyle,
    standard_banded,
    standard_whole_balance,
)


class TestBanded:
    def test_each_slice_earns_its_own_rate(self):
        product = standard_banded()
        # 10000 at 1% = 100, then 5000 at 3% = 150.
        assert product.annual_interest(Money.of(15000, "USD")) == Money.of(250, "USD")

    def test_a_balance_inside_the_first_tier(self):
        assert standard_banded().annual_interest(Money.of(5000, "USD")) == Money.of(
            50, "USD"
        )

    def test_the_blended_rate_sits_below_the_headline(self):
        product = standard_banded()
        blended = product.blended_rate(Money.of(15000, "USD"))
        assert blended < product.headline_rate()
        assert not product.beats_headline(Money.of(15000, "USD"))


class TestWholeBalance:
    def test_everything_earns_the_reached_rate(self):
        product = standard_whole_balance()
        assert product.annual_interest(Money.of(15000, "USD")) == Money.of(450, "USD")

    def test_it_jumps_at_the_threshold(self):
        product = standard_whole_balance()
        below = product.annual_interest(Money.of("9999.99", "USD"))
        above = product.annual_interest(Money.of(10000, "USD"))
        # A cent more balance nearly triples the interest, which is the
        # jump a whole-balance product creates and a banded one does not.
        assert above.units > below.units * 2

    def test_the_two_styles_genuinely_differ(self):
        balance = Money.of(15000, "USD")
        banded = standard_banded().annual_interest(balance)
        whole = standard_whole_balance().annual_interest(balance)
        assert whole > banded


class TestRates:
    def test_the_headline_is_the_top_tier(self):
        assert standard_banded().headline_rate() == Fraction(5, 100)

    def test_the_reached_rate_follows_the_balance(self):
        product = standard_banded()
        assert product.reached_rate(Money.of(5000, "USD")) == Fraction(1, 100)
        assert product.reached_rate(Money.of(60000, "USD")) == Fraction(5, 100)

    def test_a_zero_balance_has_no_blended_rate(self):
        assert standard_banded().blended_rate(Money.zero("USD")) is None

    def test_a_whole_balance_account_can_match_the_headline(self):
        product = standard_whole_balance()
        assert product.beats_headline(Money.of(60000, "USD"))


class TestConstruction:
    def test_the_first_tier_starts_at_zero(self):
        with pytest.raises(Refused):
            SavingsProduct(
                "bad",
                (RateTier(Money.of(100, "USD"), Fraction(1, 100)),),
                TierStyle.BANDED,
            )

    def test_floors_must_increase(self):
        with pytest.raises(Refused):
            SavingsProduct(
                "bad",
                (
                    RateTier(Money.zero("USD"), Fraction(1, 100)),
                    RateTier(Money.of(500, "USD"), Fraction(2, 100)),
                    RateTier(Money.of(100, "USD"), Fraction(3, 100)),
                ),
                TierStyle.BANDED,
            )

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            RateTier(Money.zero("USD"), Fraction(-1, 100))

    def test_a_negative_balance_is_refused(self):
        with pytest.raises(Refused):
            standard_banded().annual_interest(Money.of("-1.00", "USD"))

    def test_a_wrong_currency_balance_is_refused(self):
        with pytest.raises(Refused):
            standard_banded().annual_interest(Money.of(100, "EUR"))
