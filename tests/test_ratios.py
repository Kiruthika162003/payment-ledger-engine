from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.ratios import FinancialPosition


def _position(**overrides) -> FinancialPosition:
    base = {
        "current_assets": Money.of(2000, "USD"),
        "inventory": Money.of(500, "USD"),
        "current_liabilities": Money.of(1000, "USD"),
        "total_assets": Money.of(5000, "USD"),
        "total_liabilities": Money.of(2000, "USD"),
        "equity": Money.of(3000, "USD"),
        "revenue": Money.of(4000, "USD"),
        "net_income": Money.of(400, "USD"),
    }
    base.update(overrides)
    return FinancialPosition(**base)


class TestLiquidity:
    def test_the_current_ratio(self):
        assert _position().current_ratio() == Fraction(2)

    def test_the_quick_ratio_removes_inventory(self):
        assert _position().quick_ratio() == Fraction(3, 2)

    def test_working_capital_is_a_money_amount(self):
        assert _position().working_capital() == Money.of(1000, "USD")


class TestLeverage:
    def test_debt_to_equity(self):
        assert _position().debt_to_equity() == Fraction(2, 3)

    def test_the_equity_ratio(self):
        assert _position().equity_ratio() == Fraction(3, 5)

    def test_solvency(self):
        assert _position().is_solvent()
        assert not _position(total_liabilities=Money.of(9000, "USD")).is_solvent()


class TestProfitability:
    def test_net_margin(self):
        assert _position().net_margin() == Fraction(1, 10)

    def test_return_on_equity(self):
        assert _position().return_on_equity() == Fraction(2, 15)

    def test_return_on_assets(self):
        assert _position().return_on_assets() == Fraction(2, 25)


class TestUndefined:
    def test_no_current_liabilities_leaves_the_ratio_undefined(self):
        position = _position(current_liabilities=Money.zero("USD"))
        assert position.current_ratio() is None
        assert position.quick_ratio() is None

    def test_no_revenue_leaves_the_margin_undefined_not_zero(self):
        assert _position(revenue=Money.zero("USD")).net_margin() is None

    def test_the_summary_carries_the_absences(self):
        summary = _position(revenue=Money.zero("USD")).summary()
        assert summary["net_margin"] is None
        assert summary["current_ratio"] == Fraction(2)


class TestRefusals:
    def test_mixing_currencies_is_refused(self):
        with pytest.raises(Refused) as caught:
            _position(revenue=Money.of(4000, "EUR"))
        assert "mixes currencies" in str(caught.value)
