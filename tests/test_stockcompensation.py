from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.stockcompensation import (
    CompensationPlan,
    MarketConditionAward,
    ShareAward,
)


def _award(**kwargs) -> ShareAward:
    base = {
        "id": "A-1",
        "grant_date_fair_value": Money.of(10, "USD"),
        "options_granted": 1000,
        "vesting_periods": 4,
    }
    base.update(kwargs)
    return ShareAward(**base)


class TestSpreading:
    def test_the_cost_spreads_over_vesting(self):
        award = _award()
        assert award.total_expected_cost() == Money.of(10000, "USD")
        assert award.advance_period() == Money.of(2500, "USD")

    def test_it_accumulates_period_by_period(self):
        award = _award()
        for _ in range(4):
            award.advance_period()
        assert award.recognized == Money.of(10000, "USD")
        assert award.is_fully_vested()

    def test_advancing_past_vesting_is_refused(self):
        award = _award()
        for _ in range(4):
            award.advance_period()
        with pytest.raises(Refused):
            award.advance_period()

    def test_the_per_period_cost_is_reported(self):
        assert _award().cost_per_period() == Money.of(2500, "USD")


class TestTrueUp:
    def test_fewer_expected_leavers_raises_the_cumulative_cost(self):
        award = _award(expected_to_vest=800)
        award.advance_period()
        movement = award.revise_expectation(1000)
        assert movement.is_positive()

    def test_a_wave_of_leavers_produces_a_credit(self):
        award = _award()
        award.advance_period()
        award.advance_period()
        movement = award.revise_expectation(500)
        assert movement.is_negative()
        assert award.recognized == Money.of(2500, "USD")

    def test_forfeiture_revises_the_expectation(self):
        award = _award()
        award.advance_period()
        award.forfeit(200)
        assert award.expected_to_vest == 800
        assert award.recognized == Money.of(2000, "USD")

    def test_the_cumulative_cost_is_recomputed_not_incremented(self):
        award = _award()
        award.advance_period()
        award.advance_period()
        award.revise_expectation(500)
        # Half vested on 500 options at 10 each is 2500, not a patched-up sum.
        assert award.recognized == Money.of(2500, "USD")

    def test_forfeiting_more_than_granted_is_refused(self):
        with pytest.raises(Refused):
            _award().forfeit(5000)

    def test_an_impossible_expectation_is_refused(self):
        with pytest.raises(Refused):
            _award().revise_expectation(5000)


class TestMarketCondition:
    def _market(self) -> MarketConditionAward:
        return MarketConditionAward(
            id="M-1",
            grant_date_fair_value=Money.of(10, "USD"),
            options_granted=1000,
            vesting_periods=4,
        )

    def test_a_market_condition_award_still_spreads_its_cost(self):
        award = self._market()
        assert award.advance_period() == Money.of(2500, "USD")

    def test_it_is_never_trued_up(self):
        with pytest.raises(Refused) as caught:
            self._market().revise_expectation(500)
        assert "never trued up" in str(caught.value)

    def test_failing_the_target_does_not_reverse_the_cost(self):
        with pytest.raises(Refused) as caught:
            self._market().forfeit(100)
        assert "does not reverse the cost" in str(caught.value)


class TestPlan:
    def test_the_plan_totals_across_awards(self):
        plan = CompensationPlan("USD")
        plan.add(_award())
        plan.add(_award(id="A-2", options_granted=500))
        assert plan.total_expected() == Money.of(15000, "USD")
        assert plan.unrecognized() == Money.of(15000, "USD")

    def test_recognition_reduces_the_unrecognized_balance(self):
        plan = CompensationPlan("USD")
        award = plan.add(_award())
        award.advance_period()
        assert plan.total_recognized() == Money.of(2500, "USD")
        assert plan.unrecognized() == Money.of(7500, "USD")

    def test_a_wrong_currency_award_is_refused(self):
        plan = CompensationPlan("USD")
        with pytest.raises(Refused):
            plan.add(_award(grant_date_fair_value=Money.of(10, "EUR")))

    def test_a_zero_vesting_period_is_refused(self):
        with pytest.raises(Refused):
            _award(vesting_periods=0)
