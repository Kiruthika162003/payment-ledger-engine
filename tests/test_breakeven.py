from __future__ import annotations

from fractions import Fraction

import pytest

from mint.breakeven import BreakEven, Product
from mint.errors import Refused
from mint.money import Money


def _product(price: str = "25.00", cost: str = "15.00") -> Product:
    return Product("widget", Money.of(price, "USD"), Money.of(cost, "USD"))


def _model(fixed: str = "10000.00", **kwargs) -> BreakEven:
    return BreakEven(_product(**kwargs), Money.of(fixed, "USD"))


class TestContribution:
    def test_contribution_is_price_less_variable_cost(self):
        assert _product().contribution() == Money.of(10, "USD")

    def test_the_contribution_ratio(self):
        assert _product().contribution_ratio() == Fraction(2, 5)

    def test_a_product_priced_below_cost_is_not_viable(self):
        assert not _product(price="10.00", cost="15.00").is_viable()


class TestBreakEven:
    def test_the_volume_that_covers_the_fixed_costs(self):
        assert _model().units_required() == 1000

    def test_it_rounds_up_because_part_of_a_unit_covers_nothing(self):
        model = _model(fixed="10005.00")
        assert model.units_required() == 1001

    def test_the_revenue_at_break_even(self):
        assert _model().revenue_required() == Money.of(25000, "USD")

    def test_profit_is_zero_or_better_at_the_break_even_volume(self):
        model = _model()
        assert not model.profit_at(model.units_required()).is_negative()

    def test_below_break_even_is_a_loss(self):
        assert _model().profit_at(500).is_negative()


class TestNoBreakEven:
    def test_a_product_with_no_contribution_has_no_break_even(self):
        model = _model(price="15.00", cost="15.00")
        with pytest.raises(Refused) as caught:
            model.units_required()
        assert "makes the loss larger" in str(caught.value)

    def test_nor_does_it_reach_a_profit_target(self):
        model = _model(price="10.00", cost="15.00")
        with pytest.raises(Refused):
            model.units_for_target(Money.of(100, "USD"))


class TestSafetyAndLeverage:
    def test_the_margin_of_safety_above_break_even(self):
        assert _model().margin_of_safety(2000) == Fraction(1, 2)

    def test_it_goes_negative_below_break_even(self):
        assert _model().margin_of_safety(500) < 0

    def test_no_margin_at_zero_volume(self):
        assert _model().margin_of_safety(0) is None

    def test_leverage_is_extreme_near_break_even(self):
        model = _model()
        near = model.operating_leverage(1100)
        far = model.operating_leverage(5000)
        assert near > far

    def test_no_leverage_exactly_at_break_even(self):
        model = _model()
        assert model.operating_leverage(model.units_required()) is None


class TestTargets:
    def test_the_volume_for_a_profit_target(self):
        assert _model().units_for_target(Money.of(5000, "USD")) == 1500

    def test_the_price_that_breaks_even_at_a_volume(self):
        assert _model().price_for_break_even(1000) == Money.of(25, "USD")

    def test_a_zero_volume_price_is_refused(self):
        with pytest.raises(Refused):
            _model().price_for_break_even(0)


class TestConstruction:
    def test_a_zero_price_is_refused(self):
        with pytest.raises(Refused):
            _product(price="0.00")

    def test_a_negative_variable_cost_is_refused(self):
        with pytest.raises(Refused):
            _product(cost="-1.00")

    def test_negative_fixed_costs_are_refused(self):
        with pytest.raises(Refused):
            _model(fixed="-1.00")

    def test_a_negative_volume_is_refused(self):
        with pytest.raises(Refused):
            _model().profit_at(-1)
