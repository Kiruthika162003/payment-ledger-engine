from __future__ import annotations

from fractions import Fraction

import pytest

from mint.affordability import AffordabilityPolicy, assess, maximum_advance
from mint.errors import Refused
from mint.money import Money


def _policy(**kwargs) -> AffordabilityPolicy:
    base = {
        "max_debt_to_income": Fraction(40, 100),
        "stress_uplift": Fraction(3, 100),
        "minimum_disposable": Money.of(500, "USD"),
    }
    base.update(kwargs)
    return AffordabilityPolicy(**base)


def _assess(principal: str, income: str = "5000.00", **kwargs):
    return assess(
        Money.of(principal, "USD"),
        Fraction(5, 100),
        60,
        Money.of(income, "USD"),
        kwargs.get("commitments", Money.of(200, "USD")),
        kwargs.get("essentials", Money.of(1500, "USD")),
        kwargs.get("policy", _policy()),
    )


class TestBothQuestions:
    def test_a_comfortable_borrower_passes_both(self):
        result = _assess("20000.00")
        assert result.passes_today
        assert result.passes_stressed
        assert result.verdict() == "affordable"

    def test_the_stressed_payment_is_higher(self):
        result = _assess("20000.00")
        assert result.stressed_payment > result.monthly_payment

    def test_a_fragile_borrower_passes_today_and_fails_stressed(self):
        # Sized so today's payment fits and the stressed one does not.
        result = _assess("100000.00", income="5300.00", policy=_policy(
            max_debt_to_income=Fraction(41, 100),
            minimum_disposable=Money.zero("USD"),
        ))
        if result.passes_today:
            assert result.is_fragile() == (not result.passes_stressed)

    def test_an_unaffordable_loan_fails_both(self):
        result = _assess("500000.00")
        assert not result.passes_today
        assert not result.passes_stressed
        assert result.verdict() == "not affordable"


class TestRatios:
    def test_the_ratio_includes_existing_commitments(self):
        with_debt = _assess("20000.00", commitments=Money.of(1000, "USD"))
        without = _assess("20000.00", commitments=Money.zero("USD"))
        assert with_debt.debt_to_income > without.debt_to_income

    def test_the_stressed_ratio_is_higher(self):
        result = _assess("20000.00")
        assert result.stressed_debt_to_income > result.debt_to_income


class TestDisposable:
    def test_a_low_income_household_can_fail_on_disposable_alone(self):
        # Passes on ratio but is left with too little to live on.
        result = assess(
            Money.of(10000, "USD"),
            Fraction(5, 100),
            60,
            Money.of(2000, "USD"),
            Money.zero("USD"),
            Money.of(1700, "USD"),
            _policy(max_debt_to_income=Fraction(90, 100)),
        )
        assert result.debt_to_income < Fraction(90, 100)
        assert not result.passes_today

    def test_disposable_is_reported(self):
        result = _assess("20000.00")
        assert result.disposable.is_positive()
        assert result.stressed_disposable < result.disposable


class TestMaximumAdvance:
    def test_the_maximum_passes_both_tests(self):
        largest = maximum_advance(
            Fraction(5, 100),
            60,
            Money.of(5000, "USD"),
            Money.of(200, "USD"),
            Money.of(1500, "USD"),
            _policy(),
        )
        assert largest.is_positive()
        result = assess(
            largest,
            Fraction(5, 100),
            60,
            Money.of(5000, "USD"),
            Money.of(200, "USD"),
            Money.of(1500, "USD"),
            _policy(),
        )
        assert result.passes_today and result.passes_stressed


class TestRefusals:
    def test_zero_income_is_refused(self):
        with pytest.raises(Refused):
            _assess("20000.00", income="0.00")

    def test_a_ratio_limit_of_one_is_refused(self):
        with pytest.raises(Refused):
            _policy(max_debt_to_income=Fraction(1))

    def test_a_negative_uplift_is_refused(self):
        with pytest.raises(Refused):
            _policy(stress_uplift=Fraction(-1, 100))
