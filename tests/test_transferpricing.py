from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.transferpricing import (
    ArmsLengthRange,
    Method,
    PricingTest,
    comparable_price,
    cost_plus,
    markup_implied,
    profit_shifted,
    resale_minus,
)


def _range() -> ArmsLengthRange:
    return ArmsLengthRange(Money.of(90, "USD"), Money.of(110, "USD"))


class TestMethods:
    def test_cost_plus_marks_up_the_cost(self):
        assert cost_plus(Money.of(100, "USD"), Fraction(20, 100)) == Money.of(120, "USD")

    def test_resale_minus_strips_the_reseller_margin(self):
        assert resale_minus(Money.of(200, "USD"), Fraction(25, 100)) == Money.of(
            150, "USD"
        )

    def test_comparable_prices_form_a_range(self):
        observed = [Money.of(95, "USD"), Money.of(105, "USD"), Money.of(100, "USD")]
        result = comparable_price(observed)
        assert result.low == Money.of(95, "USD")
        assert result.high == Money.of(105, "USD")

    def test_no_comparables_is_refused(self):
        with pytest.raises(Refused) as caught:
            comparable_price([])
        assert "nothing to compare against" in str(caught.value)

    def test_a_negative_markup_is_refused(self):
        with pytest.raises(Refused):
            cost_plus(Money.of(100, "USD"), Fraction(-1, 10))

    def test_a_full_resale_margin_is_refused(self):
        with pytest.raises(Refused):
            resale_minus(Money.of(100, "USD"), Fraction(1))


class TestRange:
    def test_a_price_inside_the_range_passes(self):
        assert _range().contains(Money.of(100, "USD"))

    def test_a_price_below_it_does_not(self):
        assert not _range().contains(Money.of(50, "USD"))

    def test_the_distance_outside_is_measured(self):
        assert _range().distance_outside(Money.of(50, "USD")) == Money.of(40, "USD")
        assert _range().distance_outside(Money.of(100, "USD")).is_zero()

    def test_the_midpoint_is_available(self):
        assert _range().midpoint() == Money.of(100, "USD")

    def test_a_backward_range_is_refused(self):
        with pytest.raises(Refused):
            ArmsLengthRange(Money.of(110, "USD"), Money.of(90, "USD"))


class TestPricingTest:
    def test_an_arms_length_price_needs_no_adjustment(self):
        test = PricingTest(Method.COST_PLUS, Money.of(100, "USD"), _range())
        assert test.is_arms_length()
        assert test.adjustment().is_zero()
        assert "within" in test.verdict()

    def test_an_underpriced_transfer_is_adjusted_up_to_the_edge(self):
        test = PricingTest(Method.COST_PLUS, Money.of(70, "USD"), _range())
        assert not test.is_arms_length()
        assert test.adjustment() == Money.of(20, "USD")

    def test_an_overpriced_transfer_is_adjusted_down(self):
        test = PricingTest(Method.RESALE_MINUS, Money.of(130, "USD"), _range())
        assert test.adjustment() == Money.of("-20.00", "USD")

    def test_the_verdict_names_the_method_and_the_gap(self):
        test = PricingTest(Method.COMPARABLE_PRICE, Money.of(70, "USD"), _range())
        verdict = test.verdict()
        assert "comparable" in verdict
        assert "20.00" in verdict


class TestShifting:
    def test_the_implied_markup_is_computed(self):
        assert markup_implied(Money.of(100, "USD"), Money.of(120, "USD")) == Fraction(
            1, 5
        )

    def test_no_markup_without_a_cost(self):
        assert markup_implied(Money.zero("USD"), Money.of(1, "USD")) is None

    def test_profit_shifted_scales_with_volume(self):
        shifted = profit_shifted(Money.of(70, "USD"), Money.of(100, "USD"), 1000)
        assert shifted == Money.of(30000, "USD")

    def test_zero_units_is_refused(self):
        with pytest.raises(Refused):
            profit_shifted(Money.of(70, "USD"), Money.of(100, "USD"), 0)
