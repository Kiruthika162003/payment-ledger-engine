from __future__ import annotations

import datetime
from fractions import Fraction

from mint.fxrate import RateTable
from mint.money import Money
from mint.moneybag import MoneyBag, value_in

DAY = datetime.date(2026, 1, 1)


def _bag() -> MoneyBag:
    bag = MoneyBag()
    bag.add(Money.of(100, "USD"))
    bag.add(Money.of(50, "EUR"))
    bag.add(Money.of("1000", "JPY"))
    return bag


def _rates() -> RateTable:
    table = RateTable()
    table.add("EUR", "USD", Fraction(11, 10), DAY)
    table.add("JPY", "USD", Fraction(1, 150), DAY)
    return table


class TestPositions:
    def test_positions_are_kept_separately(self):
        bag = _bag()
        assert bag.balance("USD") == Money.of(100, "USD")
        assert bag.balance("EUR") == Money.of(50, "EUR")

    def test_adding_within_a_currency_is_exact(self):
        bag = MoneyBag()
        for _ in range(10):
            bag.add(Money.of("0.10", "USD"))
        assert bag.balance("USD") == Money.of(1, "USD")

    def test_currencies_lists_only_nonzero_positions(self):
        bag = _bag()
        bag.subtract(Money.of(100, "USD"))
        assert "USD" not in bag.currencies()

    def test_a_position_may_go_negative(self):
        bag = MoneyBag()
        bag.subtract(Money.of("1000", "JPY"))
        assert bag.balance("JPY").is_negative()

    def test_an_untouched_bag_is_empty(self):
        assert MoneyBag().is_empty()


class TestCombining:
    def test_merging_adds_positions(self):
        merged = _bag().merge(_bag())
        assert merged.balance("USD") == Money.of(200, "USD")

    def test_negating_flips_every_position(self):
        negated = _bag().negate()
        assert negated.balance("EUR") == Money.of("-50.00", "EUR")

    def test_holdings_lists_each_position(self):
        assert len(_bag().holdings()) == 3


class TestValuation:
    def test_a_total_needs_rates_and_a_date(self):
        valuation = value_in(_bag(), "USD", _rates(), DAY)
        # 100 USD + 50 EUR at 1.10 = 55 + 1000 JPY at 1/150 = 6.67.
        assert valuation.total == Money.of("161.67", "USD")

    def test_the_rates_used_are_reported(self):
        valuation = value_in(_bag(), "USD", _rates(), DAY)
        assert valuation.rate_for("EUR") == Fraction(11, 10)
        assert valuation.rate_for("USD") == Fraction(1)

    def test_the_valuation_carries_its_date(self):
        assert value_in(_bag(), "USD", _rates(), DAY).on == DAY
