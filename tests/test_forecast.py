from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.forecast import Method, linear_trend, run_rate, seasonal, seasonal_indices
from mint.money import Money


def _flat():
    return [Money.of(100, "USD")] * 6


def _rising():
    return [Money.of(amount, "USD") for amount in (100, 200, 300, 400)]


def _seasonal():
    # Two full cycles of four with a clear shape.
    return [
        Money.of(amount, "USD")
        for amount in (100, 200, 300, 400, 100, 200, 300, 400)
    ]


class TestRunRate:
    def test_it_repeats_the_last_period(self):
        result = run_rate(_rising(), 3)
        assert result.values == (40000, 40000, 40000)
        assert result.method is Method.RUN_RATE

    def test_it_names_its_assumption(self):
        assert "repeats unchanged" in run_rate(_flat(), 1).assumption

    def test_the_total_is_the_sum(self):
        assert run_rate(_flat(), 3).total() == Money.of(300, "USD")


class TestLinearTrend:
    def test_it_extends_a_straight_line(self):
        result = linear_trend(_rising(), 2)
        assert result.values == (50000, 60000)

    def test_a_flat_history_forecasts_flat(self):
        result = linear_trend(_flat(), 2)
        assert result.values == (10000, 10000)

    def test_it_needs_two_periods(self):
        with pytest.raises(Refused):
            linear_trend([Money.of(100, "USD")], 1)

    def test_it_names_its_assumption(self):
        assert "change per period" in linear_trend(_rising(), 1).assumption


class TestSeasonal:
    def test_the_indices_capture_the_shape(self):
        indices = seasonal_indices(_seasonal(), 4)
        assert indices[0] < indices[3]
        assert sum(indices) == 4

    def test_the_forecast_repeats_the_shape(self):
        result = seasonal(_seasonal(), 4, 4)
        assert result.values == (10000, 20000, 30000, 40000)

    def test_one_cycle_is_refused(self):
        with pytest.raises(Refused) as caught:
            seasonal_indices([Money.of(100, "USD")] * 4, 4)
        assert "just that cycle copied" in str(caught.value)

    def test_a_cycle_of_one_is_refused(self):
        with pytest.raises(Refused):
            seasonal_indices(_seasonal(), 1)

    def test_a_zero_history_has_no_shape(self):
        with pytest.raises(Refused):
            seasonal_indices([Money.zero("USD")] * 8, 4)


class TestGuards:
    def test_zero_periods_is_refused(self):
        with pytest.raises(Refused):
            run_rate(_flat(), 0)

    def test_a_mixed_currency_history_is_refused(self):
        history = [Money.of(100, "USD"), Money.of(100, "EUR")]
        with pytest.raises(Refused):
            run_rate(history, 1)

    def test_as_money_returns_typed_amounts(self):
        assert run_rate(_flat(), 2).as_money() == [Money.of(100, "USD")] * 2
