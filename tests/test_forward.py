from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.forward import (
    ForwardContract,
    forward_rate,
    hedge_ratio,
    is_over_hedged,
)
from mint.money import Money

TRADE = datetime.date(2026, 1, 1)
MATURITY = datetime.date(2026, 4, 1)


def _contract(**kwargs) -> ForwardContract:
    base = {
        "id": "F-1",
        "notional": Money.of(100000, "EUR"),
        "quote_currency": "USD",
        "agreed_rate": Fraction(110, 100),
        "trade_date": TRADE,
        "maturity": MATURITY,
    }
    base.update(kwargs)
    return ForwardContract(**base)


class TestForwardRate:
    def test_equal_rates_leave_the_forward_at_spot(self):
        rate = forward_rate(
            Fraction(110, 100), Fraction(5, 100), Fraction(5, 100), TRADE, MATURITY
        )
        assert rate == Fraction(110, 100)

    def test_a_higher_quote_rate_lifts_the_forward(self):
        rate = forward_rate(
            Fraction(110, 100), Fraction(2, 100), Fraction(6, 100), TRADE, MATURITY
        )
        assert rate > Fraction(110, 100)

    def test_a_higher_base_rate_lowers_the_forward(self):
        rate = forward_rate(
            Fraction(110, 100), Fraction(6, 100), Fraction(2, 100), TRADE, MATURITY
        )
        assert rate < Fraction(110, 100)

    def test_a_nonpositive_spot_is_refused(self):
        with pytest.raises(Refused):
            forward_rate(Fraction(0), Fraction(0), Fraction(0), TRADE, MATURITY)


class TestContract:
    def test_the_contracted_proceeds_use_the_agreed_rate(self):
        assert _contract().contracted_proceeds() == Money.of(110000, "USD")

    def test_a_weaker_market_makes_the_hedge_valuable(self):
        contract = _contract()
        assert contract.is_in_the_money(Fraction(105, 100))
        assert contract.mark_to_market(Fraction(105, 100)) == Money.of(5000, "USD")

    def test_a_stronger_market_makes_it_a_loss(self):
        contract = _contract()
        assert contract.mark_to_market(Fraction(115, 100)).is_negative()

    def test_the_position_is_visible_before_settlement(self):
        contract = _contract()
        assert not contract.has_matured(TRADE)
        assert contract.mark_to_market(Fraction(105, 100)).is_positive()

    def test_days_to_maturity_counts_down(self):
        assert _contract().days_to_maturity(TRADE) == 90
        assert _contract().days_to_maturity(MATURITY) == 0


class TestSettlement:
    def test_settling_at_maturity_realizes_the_mark(self):
        contract = _contract()
        assert contract.settle(Fraction(105, 100), MATURITY) == Money.of(5000, "USD")

    def test_settling_early_is_refused(self):
        with pytest.raises(Refused) as caught:
            _contract().settle(Fraction(105, 100), TRADE)
        assert "cannot settle before" in str(caught.value)


class TestHedgeRatio:
    def test_a_full_hedge_is_one(self):
        assert hedge_ratio(Money.of(1000, "EUR"), Money.of(1000, "EUR")) == Fraction(1)

    def test_a_partial_hedge_is_below_one(self):
        assert hedge_ratio(Money.of(1000, "EUR"), Money.of(500, "EUR")) == Fraction(1, 2)

    def test_over_hedging_is_detected(self):
        assert is_over_hedged(Money.of(1000, "EUR"), Money.of(1500, "EUR"))

    def test_no_exposure_has_no_ratio(self):
        assert hedge_ratio(Money.zero("EUR"), Money.of(100, "EUR")) is None


class TestConstruction:
    def test_maturity_must_follow_the_trade(self):
        with pytest.raises(Refused):
            _contract(maturity=TRADE)

    def test_a_forward_needs_two_currencies(self):
        with pytest.raises(Refused):
            _contract(quote_currency="EUR")

    def test_a_nonpositive_rate_is_refused(self):
        with pytest.raises(Refused):
            _contract(agreed_rate=Fraction(0))
