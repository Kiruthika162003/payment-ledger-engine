from __future__ import annotations

from fractions import Fraction

import pytest

from mint.discount import Discount, apply_discounts
from mint.errors import Refused
from mint.money import Money


class TestApply:
    def test_a_percentage_discount(self):
        result = apply_discounts(
            Money.of(100, "USD"), [Discount.of_percent(Fraction(1, 10), "10 off")]
        )
        assert result.final == Money.of(90, "USD")
        assert result.total_discount() == Money.of(10, "USD")

    def test_order_changes_the_answer(self):
        pct = Discount.of_percent(Fraction(1, 10), "10%")
        fixed = Discount.of_fixed(Money.of(5, "USD"), "5 off")
        first = apply_discounts(Money.of(100, "USD"), [pct, fixed]).final
        second = apply_discounts(Money.of(100, "USD"), [fixed, pct]).final
        # pct then fixed: 90 - 5 = 85. fixed then pct: 95 - 9.50 = 85.50.
        assert first == Money.of(85, "USD")
        assert second == Money.of("85.50", "USD")

    def test_a_coupon_larger_than_the_cart_caps_at_zero(self):
        result = apply_discounts(
            Money.of(3, "USD"), [Discount.of_fixed(Money.of(5, "USD"), "big")]
        )
        assert result.final.is_zero()
        assert result.total_discount() == Money.of(3, "USD")


class TestConstruction:
    def test_a_percentage_above_one_is_refused(self):
        with pytest.raises(Refused):
            Discount.of_percent(Fraction(3, 2), "150%")

    def test_a_negative_fixed_discount_is_refused(self):
        with pytest.raises(Refused):
            Discount.of_fixed(Money.of("-1.00", "USD"), "bad")

    def test_the_steps_are_reported(self):
        result = apply_discounts(
            Money.of(100, "USD"),
            [
                Discount.of_percent(Fraction(1, 10), "a"),
                Discount.of_fixed(Money.of(5, "USD"), "b"),
            ],
        )
        assert [name for name, _ in result.steps] == ["a", "b"]
