from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.budgetphasing import PhasedBudget, Profile, phase, variance_to_date
from mint.errors import Refused
from mint.money import Money

START = datetime.date(2026, 1, 1)
MARCH = datetime.date(2026, 3, 1)


class TestEven:
    def test_an_even_phasing_splits_the_year(self):
        budget = phase(Money.of(120000, "USD"), START, Profile.EVEN)
        assert budget.amount_for(START) == Money.of(10000, "USD")

    def test_it_sums_to_the_annual_figure(self):
        assert phase(Money.of(120000, "USD"), START).sums_to_annual()

    def test_an_awkward_annual_figure_still_sums(self):
        budget = phase(Money.of("100000.07", "USD"), START)
        assert budget.sums_to_annual()

    def test_twelve_months_are_produced(self):
        assert len(phase(Money.of(120000, "USD"), START).months) == 12


class TestProfiles:
    def test_front_loading_puts_more_in_january(self):
        budget = phase(Money.of(120000, "USD"), START, Profile.FRONT_LOADED)
        assert budget.amount_for(START) > budget.amount_for(
            datetime.date(2026, 12, 1)
        )

    def test_back_loading_reverses_it(self):
        budget = phase(Money.of(120000, "USD"), START, Profile.BACK_LOADED)
        assert budget.peak_month() == datetime.date(2026, 12, 1)

    def test_working_days_vary_by_month(self):
        budget = phase(Money.of(120000, "USD"), START, Profile.WORKING_DAYS)
        amounts = {units for _, units in budget.months}
        assert len(amounts) > 1
        assert budget.sums_to_annual()

    def test_a_seasonal_shape_is_followed(self):
        shape = [Fraction(1)] * 11 + [Fraction(5)]
        budget = phase(
            Money.of(160000, "USD"), START, Profile.SEASONAL, seasonal=shape
        )
        assert budget.peak_month() == datetime.date(2026, 12, 1)
        assert budget.sums_to_annual()

    def test_every_profile_sums_to_the_annual(self):
        for profile in (
            Profile.EVEN,
            Profile.WORKING_DAYS,
            Profile.FRONT_LOADED,
            Profile.BACK_LOADED,
        ):
            budget = phase(Money.of("99999.99", "USD"), START, profile)
            assert budget.sums_to_annual()


class TestYearToDate:
    def test_year_to_date_accumulates(self):
        budget = phase(Money.of(120000, "USD"), START)
        assert budget.year_to_date(MARCH) == Money.of(30000, "USD")

    def test_variance_compares_actual_against_the_phasing(self):
        budget = phase(Money.of(120000, "USD"), START)
        assert variance_to_date(budget, Money.of(32000, "USD"), MARCH) == Money.of(
            2000, "USD"
        )

    def test_a_seasonal_business_is_not_penalised_in_january(self):
        shape = [Fraction(1)] * 11 + [Fraction(13)]
        budget = phase(
            Money.of(240000, "USD"), START, Profile.SEASONAL, seasonal=shape
        )
        even = phase(Money.of(240000, "USD"), START, Profile.EVEN)
        assert budget.amount_for(START) < even.amount_for(START)


class TestRefusals:
    def test_a_seasonal_phasing_needs_a_shape(self):
        with pytest.raises(Refused) as caught:
            phase(Money.of(1000, "USD"), START, Profile.SEASONAL)
        assert "wearing a different name" in str(caught.value)

    def test_a_shape_of_the_wrong_length_is_refused(self):
        with pytest.raises(Refused):
            phase(
                Money.of(1000, "USD"), START, Profile.SEASONAL,
                seasonal=[Fraction(1)] * 5,
            )

    def test_a_negative_weight_is_refused(self):
        shape = [Fraction(1)] * 11 + [Fraction(-1)]
        with pytest.raises(Refused):
            phase(Money.of(1000, "USD"), START, Profile.SEASONAL, seasonal=shape)

    def test_a_nonpositive_budget_is_refused(self):
        with pytest.raises(Refused):
            phase(Money.zero("USD"), START)

    def test_a_month_outside_the_year_is_refused(self):
        budget = phase(Money.of(120000, "USD"), START)
        with pytest.raises(Refused):
            budget.amount_for(datetime.date(2030, 1, 1))

    def test_a_zero_month_budget_is_refused(self):
        with pytest.raises(Refused):
            phase(Money.of(1000, "USD"), START, months=0)

    def test_an_empty_budget_is_still_a_dataclass(self):
        budget = PhasedBudget(Money.of(100, "USD"), Profile.EVEN, ())
        assert not budget.sums_to_annual()
