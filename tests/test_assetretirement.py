from __future__ import annotations

from fractions import Fraction

import pytest

from mint.assetretirement import RetirementObligation
from mint.errors import Refused
from mint.money import Money


def _obligation(**kwargs) -> RetirementObligation:
    base = {
        "id": "PLATFORM-1",
        "asset_construction_cost": Money.of(1000000, "USD"),
        "estimated_removal_cost": Money.of(200000, "USD"),
        "rate": Fraction(5, 100),
        "life_years": 10,
    }
    base.update(kwargs)
    return RetirementObligation(**base)


class TestCapitalization:
    def test_the_removal_cost_is_added_to_the_asset(self):
        obligation = _obligation()
        assert obligation.capitalized_cost() > obligation.asset_construction_cost

    def test_it_is_added_at_present_value_not_face(self):
        obligation = _obligation()
        added = obligation.capitalized_cost() - obligation.asset_construction_cost
        assert added < obligation.estimated_removal_cost
        assert added == obligation.provision.present_value()

    def test_the_liability_starts_at_present_value(self):
        obligation = _obligation()
        assert obligation.liability() == obligation.provision.present_value()

    def test_depreciation_spreads_the_combined_cost(self):
        obligation = _obligation()
        expected = obligation.capitalized_cost().units // 10
        assert abs(obligation.annual_depreciation().units - expected) <= 1


class TestTwoLines:
    def test_a_year_produces_both_a_charge_and_a_finance_cost(self):
        obligation = _obligation()
        depreciation, finance = obligation.advance_year()
        assert depreciation.is_positive()
        assert finance.is_positive()
        assert depreciation != finance

    def test_the_liability_grows_while_the_asset_shrinks(self):
        obligation = _obligation()
        liability_before = obligation.liability()
        carrying_before = obligation.carrying_value()
        obligation.advance_year()
        assert obligation.liability() > liability_before
        assert obligation.carrying_value() < carrying_before

    def test_over_the_life_the_liability_reaches_the_removal_cost(self):
        obligation = _obligation()
        for _ in range(10):
            obligation.advance_year()
        assert obligation.is_ready_for_removal()
        assert obligation.liability() == Money.of(200000, "USD")

    def test_the_asset_fully_depreciates(self):
        obligation = _obligation()
        for _ in range(10):
            obligation.advance_year()
        assert obligation.is_fully_depreciated()

    def test_depreciating_past_the_end_is_refused(self):
        obligation = _obligation(life_years=1)
        obligation.depreciate()
        with pytest.raises(Refused):
            obligation.depreciate()

    def test_the_total_charged_covers_both(self):
        obligation = _obligation()
        obligation.advance_year()
        total = obligation.total_charged_to_date()
        assert total > obligation.accumulated_depreciation


class TestRevision:
    def test_a_raised_estimate_increases_the_liability(self):
        obligation = _obligation()
        movement = obligation.revise_estimate(Money.of(300000, "USD"))
        assert movement.is_positive()
        assert obligation.liability_at_removal() == Money.of(300000, "USD")

    def test_a_lowered_estimate_reduces_it(self):
        obligation = _obligation()
        assert obligation.revise_estimate(Money.of(100000, "USD")).is_negative()

    def test_a_nonpositive_estimate_is_refused(self):
        with pytest.raises(Refused):
            _obligation().revise_estimate(Money.zero("USD"))


class TestConstruction:
    def test_a_nonpositive_build_cost_is_refused(self):
        with pytest.raises(Refused):
            _obligation(asset_construction_cost=Money.zero("USD"))

    def test_a_nonpositive_removal_estimate_is_refused(self):
        with pytest.raises(Refused):
            _obligation(estimated_removal_cost=Money.zero("USD"))

    def test_a_zero_life_is_refused(self):
        with pytest.raises(Refused):
            _obligation(life_years=0)

    def test_mixed_currencies_are_refused(self):
        with pytest.raises(Refused):
            _obligation(estimated_removal_cost=Money.of(1000, "EUR"))
