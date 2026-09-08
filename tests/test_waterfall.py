from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.waterfall import UNEXPLAINED, Waterfall


def _waterfall() -> Waterfall:
    return Waterfall(opening=Money.of(1000, "USD"), closing=Money.of(1150, "USD"))


class TestReconciliation:
    def test_a_complete_waterfall_reconciles(self):
        waterfall = _waterfall()
        waterfall.add("new", Money.of(300, "USD"))
        waterfall.add("churn", Money.of("-150.00", "USD"))
        assert waterfall.reconciles()
        assert waterfall.residual().is_zero()

    def test_an_incomplete_waterfall_refuses_to_build(self):
        waterfall = _waterfall()
        waterfall.add("new", Money.of(100, "USD"))
        with pytest.raises(Refused) as caught:
            waterfall.build()
        assert "drawing a chart that misleads" in str(caught.value)

    def test_the_gap_can_be_named_honestly(self):
        waterfall = _waterfall()
        waterfall.add("new", Money.of(100, "USD"))
        step = waterfall.close_with_unexplained()
        assert step.name == UNEXPLAINED
        assert step.amount == Money.of(50, "USD")
        assert waterfall.reconciles()

    def test_closing_a_complete_waterfall_adds_nothing(self):
        waterfall = _waterfall()
        waterfall.add("new", Money.of(150, "USD"))
        assert waterfall.close_with_unexplained() is None


class TestPresentation:
    def test_running_totals_walk_from_opening_to_closing(self):
        waterfall = _waterfall()
        waterfall.add("new", Money.of(300, "USD"))
        waterfall.add("churn", Money.of("-150.00", "USD"))
        rows = waterfall.build()
        assert rows[0] == ("opening", 100000)
        assert rows[-1] == ("closing", 115000)
        assert rows[1] == ("new", 130000)

    def test_increases_and_decreases_are_separated(self):
        waterfall = _waterfall()
        waterfall.add("new", Money.of(300, "USD"))
        waterfall.add("churn", Money.of("-150.00", "USD"))
        assert [s.name for s in waterfall.increases()] == ["new"]
        assert [s.name for s in waterfall.decreases()] == ["churn"]

    def test_the_largest_step_is_named(self):
        waterfall = _waterfall()
        waterfall.add("new", Money.of(300, "USD"))
        waterfall.add("churn", Money.of("-150.00", "USD"))
        assert waterfall.largest_step().name == "new"

    def test_an_empty_waterfall_has_no_largest_step(self):
        assert _waterfall().largest_step() is None


class TestRefusals:
    def test_an_unnamed_step_is_refused(self):
        with pytest.raises(Refused):
            _waterfall().add("  ", Money.of(10, "USD"))

    def test_a_wrong_currency_step_is_refused(self):
        with pytest.raises(Refused):
            _waterfall().add("x", Money.of(10, "EUR"))
