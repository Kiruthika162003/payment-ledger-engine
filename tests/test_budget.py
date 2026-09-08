from __future__ import annotations

from fractions import Fraction

import pytest

from mint.budget import BudgetReport, Direction
from mint.errors import Refused
from mint.money import Money


def _report() -> BudgetReport:
    report = BudgetReport("USD")
    report.add("4000", "Sales", Money.of(1000, "USD"), Money.of(1200, "USD"),
               Direction.MORE_IS_BETTER)
    report.add("5000", "Rent", Money.of(500, "USD"), Money.of(450, "USD"),
               Direction.LESS_IS_BETTER)
    report.add("5100", "Travel", Money.of(200, "USD"), Money.of(350, "USD"),
               Direction.LESS_IS_BETTER)
    return report


class TestDirection:
    def test_revenue_over_budget_is_favorable(self):
        line = _report().lines[0]
        assert line.is_favorable()
        assert line.verdict() == "favorable"

    def test_expense_under_budget_is_favorable(self):
        line = _report().lines[1]
        assert line.is_favorable()
        assert line.variance() == Money.of("-50.00", "USD")

    def test_expense_over_budget_is_unfavorable(self):
        line = _report().lines[2]
        assert not line.is_favorable()
        assert line.verdict() == "unfavorable"

    def test_hitting_the_budget_exactly_reads_on_budget(self):
        report = BudgetReport("USD")
        line = report.add(
            "5000", "Rent", Money.of(500, "USD"), Money.of(500, "USD"),
            Direction.LESS_IS_BETTER,
        )
        assert line.verdict() == "on budget"


class TestTotals:
    def test_totals_foot(self):
        report = _report()
        assert report.total_budget() == Money.of(1700, "USD")
        assert report.total_actual() == Money.of(2000, "USD")
        assert report.total_variance() == Money.of(300, "USD")

    def test_the_unfavorable_lines_are_listed(self):
        assert [line.code for line in _report().unfavorable()] == ["5100"]

    def test_the_worst_line_is_the_largest_unfavorable(self):
        assert _report().worst_line().code == "5100"

    def test_a_clean_report_has_no_worst_line(self):
        report = BudgetReport("USD")
        report.add("4000", "Sales", Money.of(100, "USD"), Money.of(150, "USD"),
                   Direction.MORE_IS_BETTER)
        assert report.worst_line() is None


class TestPercent:
    def test_percent_is_against_the_budget(self):
        assert _report().lines[0].percent_of_budget() == Fraction(1, 5)

    def test_a_zero_budget_has_no_percentage(self):
        report = BudgetReport("USD")
        line = report.add("9000", "New", Money.zero("USD"), Money.of(10, "USD"),
                          Direction.LESS_IS_BETTER)
        assert line.percent_of_budget() is None


class TestRefusals:
    def test_a_wrong_currency_line_is_refused(self):
        with pytest.raises(Refused):
            _report().add("6000", "X", Money.of(10, "EUR"), Money.of(10, "EUR"),
                          Direction.LESS_IS_BETTER)
