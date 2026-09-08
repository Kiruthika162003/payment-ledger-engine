from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.factoring import FactoringTerms, effective_annual_cost, factor
from mint.money import Money


def _terms(with_recourse: bool = False) -> FactoringTerms:
    return FactoringTerms(
        advance_rate=Fraction(80, 100),
        discount_rate=Fraction(3, 100),
        with_recourse=with_recourse,
    )


class TestAdvance:
    def test_the_advance_is_the_stated_fraction(self):
        result = factor(Money.of(10000, "USD"), _terms())
        assert result.advance == Money.of(8000, "USD")
        assert result.cash_today() == Money.of(8000, "USD")

    def test_the_reserve_is_the_rest(self):
        result = factor(Money.of(10000, "USD"), _terms())
        assert result.reserve == Money.of(2000, "USD")

    def test_the_fee_comes_out_of_the_reserve(self):
        result = factor(Money.of(10000, "USD"), _terms())
        assert result.fee == Money.of(300, "USD")
        assert result.reserve_released() == Money.of(1700, "USD")

    def test_the_pieces_reconcile_to_the_face(self):
        result = factor(Money.of(10000, "USD"), _terms())
        assert result.reconciles()
        assert result.cost() == Money.of(300, "USD")


class TestRecourse:
    def test_non_recourse_removes_the_asset(self):
        result = factor(Money.of(10000, "USD"), _terms(with_recourse=False))
        assert not result.stays_on_balance_sheet()

    def test_recourse_keeps_the_asset_on_the_books(self):
        result = factor(Money.of(10000, "USD"), _terms(with_recourse=True))
        assert result.stays_on_balance_sheet()


class TestCost:
    def test_the_annualized_cost_scales_with_the_wait(self):
        result = factor(Money.of(10000, "USD"), _terms())
        quick = effective_annual_cost(result, 30)
        slow = effective_annual_cost(result, 90)
        assert quick > slow

    def test_no_cost_measure_without_days(self):
        result = factor(Money.of(10000, "USD"), _terms())
        assert effective_annual_cost(result, 0) is None


class TestRefusals:
    def test_a_fee_larger_than_the_reserve_is_refused(self):
        terms = FactoringTerms(
            advance_rate=Fraction(99, 100),
            discount_rate=Fraction(5, 100),
            with_recourse=False,
        )
        with pytest.raises(Refused) as caught:
            factor(Money.of(10000, "USD"), terms)
        assert "would owe the factor money" in str(caught.value)

    def test_an_advance_above_one_is_refused(self):
        with pytest.raises(Refused):
            FactoringTerms(Fraction(3, 2), Fraction(1, 100), False)

    def test_a_nonpositive_receivable_is_refused(self):
        with pytest.raises(Refused):
            factor(Money.zero("USD"), _terms())
