from __future__ import annotations

from fractions import Fraction

import pytest

from mint.annuity import (
    AnnuityTerms,
    advantage_of_paying_in_advance,
    future_value,
    future_value_factor,
    payment_for_future_value,
    payment_for_present_value,
    present_value,
    present_value_factor,
)
from mint.errors import Refused
from mint.money import Money


class TestFactors:
    def test_a_zero_rate_factor_is_just_the_count(self):
        assert present_value_factor(Fraction(0), 12) == Fraction(12)
        assert future_value_factor(Fraction(0), 12) == Fraction(12)

    def test_a_due_factor_is_one_period_larger(self):
        rate = Fraction(1, 100)
        ordinary = present_value_factor(rate, 12)
        due = present_value_factor(rate, 12, due=True)
        assert due == ordinary * (1 + rate)


class TestValues:
    def test_present_value_of_a_stream(self):
        terms = AnnuityTerms(Money.of(100, "USD"), Fraction(1, 100), 12)
        assert present_value(terms) == Money.from_minor(112551, "USD")

    def test_future_value_of_a_stream(self):
        terms = AnnuityTerms(Money.of(100, "USD"), Fraction(1, 100), 12)
        assert future_value(terms) == Money.from_minor(126825, "USD")

    def test_paying_in_advance_is_worth_more(self):
        terms = AnnuityTerms(Money.of(100, "USD"), Fraction(1, 100), 12, due=True)
        arrears = AnnuityTerms(Money.of(100, "USD"), Fraction(1, 100), 12)
        assert present_value(terms) > present_value(arrears)

    def test_the_advantage_is_one_periods_growth(self):
        # Exactly one period's growth on the ordinary value is 1125.51 in
        # cents, but each present value rounds on its own before they are
        # subtracted, so the measured difference is 1125, not 1126.
        terms = AnnuityTerms(Money.of(100, "USD"), Fraction(1, 100), 12)
        assert advantage_of_paying_in_advance(terms) == Money.from_minor(1125, "USD")

    def test_a_zero_rate_stream_is_just_the_sum(self):
        terms = AnnuityTerms(Money.of(100, "USD"), Fraction(0), 12)
        assert present_value(terms) == Money.of(1200, "USD")


class TestSolving:
    def test_the_payment_that_funds_a_present_value(self):
        payment = payment_for_present_value(
            Money.from_minor(112551, "USD"), Fraction(1, 100), 12
        )
        assert payment == Money.of(100, "USD")

    def test_the_payment_that_accumulates_a_target(self):
        payment = payment_for_future_value(
            Money.from_minor(126825, "USD"), Fraction(1, 100), 12
        )
        assert payment == Money.of(100, "USD")


class TestRefusals:
    def test_zero_periods_is_refused(self):
        with pytest.raises(Refused):
            AnnuityTerms(Money.of(100, "USD"), Fraction(1, 100), 0)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            AnnuityTerms(Money.of(100, "USD"), Fraction(-1, 100), 12)

    def test_a_nonpositive_target_is_refused(self):
        with pytest.raises(Refused):
            payment_for_present_value(Money.zero("USD"), Fraction(1, 100), 12)
