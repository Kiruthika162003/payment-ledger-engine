from __future__ import annotations

import datetime

import pytest

from mint.barter import BarterExchange, Measurability
from mint.errors import Refused
from mint.money import Money

DAY = datetime.date(2026, 6, 1)


def _exchange(**kwargs) -> BarterExchange:
    base = {
        "id": "X-1",
        "date": DAY,
        "book_value_given": Money.of(10000, "USD"),
        "fair_value_given": Money.of(15000, "USD"),
        "fair_value_received": Money.of(16000, "USD"),
    }
    base.update(kwargs)
    return BarterExchange(**base)


class TestWithSubstance:
    def test_it_records_at_the_fair_value_given(self):
        result = _exchange().record()
        assert result.recorded_value == Money.of(15000, "USD")
        assert result.has_substance

    def test_the_gain_is_the_uplift_over_book_value(self):
        result = _exchange().record()
        assert result.gain == Money.of(5000, "USD")
        assert result.is_gain()

    def test_it_reconciles_against_the_book_value(self):
        exchange = _exchange()
        assert exchange.record().reconciles(exchange.book_value_given)

    def test_the_received_side_can_be_the_measurable_one(self):
        exchange = _exchange(measurability=Measurability.RECEIVED_MORE_RELIABLE)
        result = exchange.record()
        assert result.recorded_value == Money.of(16000, "USD")
        assert "received" in result.basis


class TestWithoutSubstance:
    def test_nothing_changed_so_no_gain_is_recognized(self):
        exchange = _exchange(changes_cash_flows=False)
        result = exchange.record()
        assert result.gain.is_zero()
        assert not result.has_substance

    def test_it_carries_over_at_book_value(self):
        exchange = _exchange(changes_cash_flows=False)
        assert exchange.record().recorded_value == Money.of(10000, "USD")

    def test_the_basis_says_why(self):
        exchange = _exchange(changes_cash_flows=False)
        assert "lacking substance" in exchange.record().basis

    def test_the_advertising_swap_pattern_is_detected(self):
        exchange = _exchange(changes_cash_flows=False)
        assert exchange.would_inflate_revenue(Money.of(500000, "USD"))

    def test_a_substantive_exchange_is_not_flagged(self):
        assert not _exchange().would_inflate_revenue(Money.of(500000, "USD"))


class TestMeasurability:
    def test_an_unmeasurable_exchange_is_refused(self):
        exchange = _exchange(measurability=Measurability.NEITHER_RELIABLE)
        with pytest.raises(Refused) as caught:
            exchange.record()
        assert "nothing behind it" in str(caught.value)

    def test_a_missing_fair_value_on_the_claimed_side_is_refused(self):
        exchange = _exchange(fair_value_given=None)
        with pytest.raises(Refused):
            exchange.record()

    def test_a_missing_received_value_is_refused_when_claimed(self):
        exchange = _exchange(
            fair_value_received=None,
            measurability=Measurability.RECEIVED_MORE_RELIABLE,
        )
        with pytest.raises(Refused):
            exchange.record()


class TestConstruction:
    def test_a_negative_book_value_is_refused(self):
        with pytest.raises(Refused):
            _exchange(book_value_given=Money.of("-1.00", "USD"))

    def test_a_negative_fair_value_is_refused(self):
        with pytest.raises(Refused):
            _exchange(fair_value_given=Money.of("-1.00", "USD"))

    def test_a_mixed_currency_exchange_is_refused(self):
        with pytest.raises(Refused):
            _exchange(fair_value_given=Money.of(100, "EUR"))

    def test_the_gain_helper_matches_the_record(self):
        exchange = _exchange()
        assert exchange.gain_if_recognized() == exchange.record().gain
