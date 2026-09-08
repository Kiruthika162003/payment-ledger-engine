from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.workingcapital import WorkingCapital, improvement


def _capital(**kwargs) -> WorkingCapital:
    base = {
        "receivables": Money.of(100000, "USD"),
        "inventory": Money.of(50000, "USD"),
        "payables": Money.of(60000, "USD"),
        "revenue": Money.of(730000, "USD"),
        "cost_of_sales": Money.of(365000, "USD"),
    }
    base.update(kwargs)
    return WorkingCapital(**base)


class TestDays:
    def test_days_sales_outstanding(self):
        assert _capital().days_sales_outstanding() == Fraction(50)

    def test_days_inventory_outstanding(self):
        assert _capital().days_inventory_outstanding() == Fraction(50)

    def test_days_payable_outstanding(self):
        assert _capital().days_payable_outstanding() == Fraction(60)

    def test_the_cycle_subtracts_supplier_credit(self):
        assert _capital().cash_conversion_cycle() == Fraction(40)


class TestSelfFunding:
    def test_a_long_payable_period_can_fund_the_whole_cycle(self):
        capital = _capital(payables=Money.of(200000, "USD"))
        assert capital.is_self_funding()
        assert capital.cash_conversion_cycle() < 0

    def test_a_normal_business_funds_its_own_gap(self):
        assert not _capital().is_self_funding()

    def test_the_verdict_reads_plainly(self):
        assert "normal cycle" in _capital().verdict()

    def test_a_long_cycle_is_named(self):
        capital = _capital(receivables=Money.of(400000, "USD"))
        assert "quarter or more" in capital.verdict()


class TestUnmeasurable:
    def test_no_revenue_leaves_days_sales_undefined(self):
        capital = _capital(revenue=Money.zero("USD"))
        assert capital.days_sales_outstanding() is None
        assert capital.cash_conversion_cycle() is None

    def test_no_cost_of_sales_leaves_the_other_two_undefined(self):
        capital = _capital(cost_of_sales=Money.zero("USD"))
        assert capital.days_inventory_outstanding() is None
        assert capital.days_payable_outstanding() is None

    def test_the_verdict_says_so(self):
        capital = _capital(revenue=Money.zero("USD"))
        assert "not enough activity" in capital.verdict()

    def test_no_funding_gap_without_a_cycle(self):
        assert _capital(revenue=Money.zero("USD")).funding_gap() is None


class TestAmounts:
    def test_working_capital_is_the_balance_sum(self):
        assert _capital().working_capital() == Money.of(90000, "USD")

    def test_the_funding_gap_scales_with_daily_revenue(self):
        gap = _capital().funding_gap()
        assert gap is not None
        assert gap.is_positive()

    def test_improvement_measures_the_change(self):
        before = _capital()
        after = _capital(receivables=Money.of(60000, "USD"))
        assert improvement(before, after) == Fraction(20)

    def test_no_improvement_without_both_cycles(self):
        assert improvement(_capital(), _capital(revenue=Money.zero("USD"))) is None


class TestRefusals:
    def test_mixed_currencies_are_refused(self):
        with pytest.raises(Refused):
            _capital(inventory=Money.of(1, "EUR"))

    def test_a_negative_balance_is_refused(self):
        with pytest.raises(Refused):
            _capital(inventory=Money.of("-1.00", "USD"))

    def test_a_zero_length_period_is_refused(self):
        with pytest.raises(Refused):
            _capital(days_in_period=0)
