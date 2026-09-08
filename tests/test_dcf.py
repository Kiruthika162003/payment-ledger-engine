from __future__ import annotations

from fractions import Fraction

import pytest

from mint.dcf import (
    CashFlow,
    internal_rate_of_return,
    net_present_value,
    payback_period,
    profitability_index,
    sign_changes,
)
from mint.errors import Refused
from mint.money import Money


def _project():
    return [
        CashFlow(0, Money.of("-1000.00", "USD")),
        CashFlow(1, Money.of(400, "USD")),
        CashFlow(2, Money.of(400, "USD")),
        CashFlow(3, Money.of(400, "USD")),
    ]


class TestNpv:
    def test_a_zero_rate_is_just_the_sum(self):
        assert net_present_value(_project(), Fraction(0), "USD") == Money.of(200, "USD")

    def test_discounting_lowers_the_value(self):
        discounted = net_present_value(_project(), Fraction(10, 100), "USD")
        assert discounted < Money.of(200, "USD")

    def test_a_high_rate_turns_it_negative(self):
        assert net_present_value(_project(), Fraction(50, 100), "USD").is_negative()

    def test_a_mixed_currency_stream_is_refused(self):
        flows = [*_project(), CashFlow(4, Money.of(100, "EUR"))]
        with pytest.raises(Refused):
            net_present_value(flows, Fraction(1, 10), "USD")


class TestIrr:
    def test_the_rate_zeroes_the_npv(self):
        rate = internal_rate_of_return(_project())
        residual = net_present_value(_project(), rate, "USD")
        assert abs(residual.units) <= 1

    def test_the_rate_is_plausible(self):
        rate = internal_rate_of_return(_project())
        assert Fraction(9, 100) < rate < Fraction(11, 100)

    def test_an_all_positive_stream_has_no_return(self):
        flows = [CashFlow(0, Money.of(100, "USD")), CashFlow(1, Money.of(100, "USD"))]
        with pytest.raises(Refused) as caught:
            internal_rate_of_return(flows)
        assert "no return" in str(caught.value)

    def test_an_empty_stream_is_refused(self):
        with pytest.raises(Refused):
            internal_rate_of_return([])

    def test_a_bracket_without_a_sign_change_is_refused(self):
        with pytest.raises(Refused) as caught:
            internal_rate_of_return(
                _project(), low=Fraction(50, 100), high=Fraction(90, 100)
            )
        assert "bracket" in str(caught.value)


class TestSupporting:
    def test_sign_changes_are_counted(self):
        assert sign_changes(_project()) == 1

    def test_the_payback_period(self):
        assert payback_period(_project()) == 3

    def test_a_project_that_never_pays_back(self):
        flows = [CashFlow(0, Money.of("-1000.00", "USD")), CashFlow(1, Money.of(10, "USD"))]
        assert payback_period(flows) is None

    def test_the_profitability_index_exceeds_one_when_worthwhile(self):
        index = profitability_index(_project(), Fraction(0), "USD")
        assert index > 1

    def test_no_index_without_an_outflow(self):
        flows = [CashFlow(1, Money.of(100, "USD"))]
        assert profitability_index(flows, Fraction(0), "USD") is None

    def test_a_negative_period_is_refused(self):
        with pytest.raises(Refused):
            CashFlow(-1, Money.of(1, "USD"))
