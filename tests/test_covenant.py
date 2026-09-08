from __future__ import annotations

from fractions import Fraction

import pytest

from mint.covenant import CovenantSuite, Direction, ebitda_headroom
from mint.errors import Refused
from mint.money import Money


def _suite(**kwargs) -> CovenantSuite:
    base = {
        "currency": "USD",
        "ebitda": Money.of(1000000, "USD"),
        "net_debt": Money.of(2500000, "USD"),
        "interest_expense": Money.of(250000, "USD"),
        "net_worth": Money.of(500000, "USD"),
    }
    base.update(kwargs)
    return CovenantSuite(**base)


class TestMetrics:
    def test_leverage_is_debt_over_earnings(self):
        assert _suite().leverage() == Fraction(5, 2)

    def test_interest_cover_is_earnings_over_interest(self):
        assert _suite().interest_cover() == Fraction(4)


class TestTesting:
    def test_a_passing_leverage_test_reports_headroom(self):
        result = _suite().test_leverage(Fraction(3))
        assert result.passes()
        assert result.headroom() == Fraction(1, 2)

    def test_a_breached_test_reports_negative_headroom(self):
        result = _suite().test_leverage(Fraction(2))
        assert not result.passes()
        assert result.headroom() == Fraction(-1, 2)
        assert "breached" in result.verdict()

    def test_an_at_least_test_measures_the_other_way(self):
        result = _suite().test_interest_cover(Fraction(3))
        assert result.direction is Direction.AT_LEAST
        assert result.headroom() == Fraction(1)

    def test_a_net_worth_test_uses_amounts(self):
        result = _suite().test_net_worth(Money.of(400000, "USD"))
        assert result.passes()


class TestUntestable:
    def test_zero_earnings_makes_leverage_untestable(self):
        suite = _suite(ebitda=Money.zero("USD"))
        result = suite.test_leverage(Fraction(3))
        assert not result.is_testable()
        assert not result.passes()

    def test_untestable_is_not_the_same_as_passing(self):
        suite = _suite(ebitda=Money.zero("USD"))
        result = suite.test_leverage(Fraction(3))
        assert "not the same as passing" in result.verdict()

    def test_zero_interest_makes_cover_untestable(self):
        suite = _suite(interest_expense=Money.zero("USD"))
        assert suite.test_interest_cover(Fraction(2)).is_testable() is False

    def test_untestable_results_are_listed(self):
        suite = _suite(ebitda=Money.zero("USD"))
        suite.test_leverage(Fraction(3))
        assert len(suite.untestable()) == 1


class TestSuite:
    def test_all_pass_when_every_test_passes(self):
        suite = _suite()
        suite.test_leverage(Fraction(3))
        suite.test_interest_cover(Fraction(3))
        assert suite.all_pass()
        assert not suite.is_accelerable()

    def test_one_breach_makes_the_loan_accelerable(self):
        suite = _suite()
        suite.test_leverage(Fraction(2))
        suite.test_interest_cover(Fraction(3))
        assert not suite.all_pass()
        assert suite.is_accelerable()
        assert len(suite.breaches()) == 1

    def test_the_tightest_test_is_named(self):
        suite = _suite()
        suite.test_leverage(Fraction(3))
        suite.test_interest_cover(Fraction(39, 10))
        assert suite.tightest().name == "interest cover"

    def test_no_tightest_without_testable_results(self):
        assert _suite().tightest() is None


class TestHeadroomAmount:
    def test_earnings_headroom_before_a_leverage_breach(self):
        headroom = ebitda_headroom(_suite(), Fraction(3))
        assert headroom.is_positive()

    def test_a_tight_limit_leaves_negative_headroom(self):
        assert ebitda_headroom(_suite(), Fraction(2)).is_negative()

    def test_a_nonpositive_limit_is_refused(self):
        with pytest.raises(Refused):
            ebitda_headroom(_suite(), Fraction(0))

    def test_mixed_currencies_are_refused(self):
        with pytest.raises(Refused):
            _suite(net_debt=Money.of(1, "EUR"))
