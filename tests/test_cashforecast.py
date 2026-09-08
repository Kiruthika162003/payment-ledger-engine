from __future__ import annotations

from fractions import Fraction

import pytest

from mint.cashforecast import CashForecast
from mint.errors import Refused
from mint.money import Money


def _forecast(opening: str = "50000.00") -> CashForecast:
    return CashForecast(currency="USD", opening=Money.of(opening, "USD"))


class TestProjection:
    def test_the_balance_walks_week_by_week(self):
        forecast = _forecast()
        forecast.add_receipt(1, "customer", Money.of(20000, "USD"))
        forecast.add_payment(1, "payroll", Money.of(30000, "USD"))
        assert forecast.balances()[0] == Money.of(40000, "USD")

    def test_the_horizon_defaults_to_thirteen_weeks(self):
        assert len(_forecast().balances()) == 13

    def test_the_closing_balance_is_the_last_week(self):
        forecast = _forecast()
        forecast.add_payment(2, "rent", Money.of(10000, "USD"))
        assert forecast.closing() == Money.of(40000, "USD")


class TestRunningOut:
    def test_the_first_negative_week_is_reported(self):
        forecast = _forecast("10000.00")
        forecast.add_payment(1, "payroll", Money.of(6000, "USD"))
        forecast.add_payment(2, "payroll", Money.of(6000, "USD"))
        assert forecast.first_negative_week() == 2
        assert not forecast.survives()

    def test_a_solvent_forecast_survives(self):
        forecast = _forecast()
        forecast.add_payment(1, "rent", Money.of(1000, "USD"))
        assert forecast.survives()
        assert forecast.first_negative_week() is None

    def test_a_dip_that_recovers_still_needs_funding(self):
        forecast = _forecast("10000.00")
        forecast.add_payment(1, "big bill", Money.of(15000, "USD"))
        forecast.add_receipt(3, "big customer", Money.of(30000, "USD"))
        assert forecast.survives() is False
        assert forecast.lowest_point().is_negative()
        assert forecast.closing().is_positive()

    def test_the_shortfall_to_fund_is_the_deepest_point(self):
        forecast = _forecast("10000.00")
        forecast.add_payment(1, "big bill", Money.of(15000, "USD"))
        assert forecast.shortfall_to_fund() == Money.of(5000, "USD")

    def test_a_solvent_forecast_needs_no_funding(self):
        assert _forecast().shortfall_to_fund().is_zero()


class TestProbability:
    def test_an_uncertain_receipt_is_weighted_down(self):
        forecast = _forecast()
        forecast.add_receipt(
            1, "shaky customer", Money.of(10000, "USD"), probability=Fraction(1, 2)
        )
        assert forecast.closing() == Money.of(55000, "USD")

    def test_the_unweighted_view_is_still_available(self):
        forecast = _forecast()
        forecast.add_receipt(
            1, "shaky customer", Money.of(10000, "USD"), probability=Fraction(1, 2)
        )
        assert forecast.closing(weighted=False) == Money.of(60000, "USD")

    def test_the_optimism_gap_is_visible(self):
        forecast = _forecast()
        forecast.add_receipt(
            1, "shaky customer", Money.of(10000, "USD"), probability=Fraction(1, 2)
        )
        assert forecast.optimism_gap() == Money.of(5000, "USD")

    def test_weighting_can_change_whether_it_survives(self):
        forecast = _forecast("1000.00")
        forecast.add_receipt(
            1, "hopeful", Money.of(10000, "USD"), probability=Fraction(1, 10)
        )
        forecast.add_payment(1, "certain bill", Money.of(5000, "USD"))
        assert not forecast.survives()
        assert forecast.survives(weighted=False)


class TestRefusals:
    def test_a_week_past_the_horizon_is_refused(self):
        with pytest.raises(Refused) as caught:
            _forecast().add_payment(20, "far off", Money.of(1, "USD"))
        assert "guesses rather than a forecast" in str(caught.value)

    def test_a_wrong_currency_flow_is_refused(self):
        with pytest.raises(Refused):
            _forecast().add_payment(1, "euro bill", Money.of(1, "EUR"))

    def test_a_nonpositive_flow_is_refused(self):
        with pytest.raises(Refused):
            _forecast().add_payment(1, "nothing", Money.zero("USD"))

    def test_a_zero_probability_is_refused(self):
        with pytest.raises(Refused):
            _forecast().add_receipt(
                1, "never", Money.of(1, "USD"), probability=Fraction(0)
            )

    def test_a_zero_week_horizon_is_refused(self):
        with pytest.raises(Refused):
            CashForecast(currency="USD", opening=Money.zero("USD"), weeks=0)
