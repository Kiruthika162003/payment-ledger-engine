from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.kpis import Subscription, arr, lifetime_value, movement, mrr
from mint.money import Money


class TestNormalization:
    def test_an_annual_plan_contributes_a_twelfth_a_month(self):
        annual = Subscription("c1", Money.of(1200, "USD"), 12)
        assert annual.monthly_value() == Money.of(100, "USD")

    def test_a_monthly_plan_contributes_its_whole_price(self):
        monthly = Subscription("c1", Money.of(50, "USD"), 1)
        assert monthly.monthly_value() == Money.of(50, "USD")

    def test_mrr_sums_normalized_values(self):
        subs = [
            Subscription("c1", Money.of(1200, "USD"), 12),
            Subscription("c2", Money.of(50, "USD"), 1),
        ]
        assert mrr(subs, "USD") == Money.of(150, "USD")

    def test_arr_is_twelve_times_mrr(self):
        subs = [Subscription("c1", Money.of(50, "USD"), 1)]
        assert arr(subs, "USD") == Money.of(600, "USD")


class TestMovement:
    def _sets(self):
        opening = [
            Subscription("stay", Money.of(100, "USD"), 1),
            Subscription("grow", Money.of(100, "USD"), 1),
            Subscription("shrink", Money.of(100, "USD"), 1),
            Subscription("leave", Money.of(100, "USD"), 1),
        ]
        closing = [
            Subscription("stay", Money.of(100, "USD"), 1),
            Subscription("grow", Money.of(180, "USD"), 1),
            Subscription("shrink", Money.of(60, "USD"), 1),
            Subscription("new", Money.of(70, "USD"), 1),
        ]
        return opening, closing

    def test_the_four_movements_are_separated(self):
        opening, closing = self._sets()
        result = movement(opening, closing, "USD")
        assert result.new == Money.of(70, "USD")
        assert result.expansion == Money.of(80, "USD")
        assert result.contraction == Money.of(40, "USD")
        assert result.churn == Money.of(100, "USD")

    def test_the_movements_reconcile_to_the_change(self):
        opening, closing = self._sets()
        result = movement(opening, closing, "USD")
        assert result.reconciles()
        assert result.net_change() == Money.of(10, "USD")

    def test_churn_is_measured_against_the_opening_base(self):
        opening, closing = self._sets()
        result = movement(opening, closing, "USD")
        assert result.churn_rate() == Fraction(100, 400)

    def test_an_empty_base_has_no_rate(self):
        result = movement([], [Subscription("a", Money.of(10, "USD"), 1)], "USD")
        assert result.churn_rate() is None
        assert result.growth_rate() is None


class TestLifetimeValue:
    def test_value_is_monthly_over_churn(self):
        assert lifetime_value(Money.of(100, "USD"), Fraction(1, 20)) == Money.of(2000, "USD")

    def test_zero_churn_has_no_finite_lifetime(self):
        with pytest.raises(Refused) as caught:
            lifetime_value(Money.of(100, "USD"), Fraction(0))
        assert "no finite lifetime" in str(caught.value)


class TestRefusals:
    def test_a_zero_month_period_is_refused(self):
        with pytest.raises(Refused):
            Subscription("c1", Money.of(10, "USD"), 0)

    def test_a_wrong_currency_subscription_is_refused(self):
        with pytest.raises(Refused):
            mrr([Subscription("c1", Money.of(10, "EUR"), 1)], "USD")
