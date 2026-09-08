from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.translation import ForeignStatements, translate


def _statements() -> ForeignStatements:
    return ForeignStatements(
        assets=Money.of(1000, "EUR"),
        liabilities=Money.of(400, "EUR"),
        contributed_equity=Money.of(500, "EUR"),
        retained_earnings=Money.of(100, "EUR"),
        revenue=Money.of(800, "EUR"),
        expenses=Money.of(700, "EUR"),
    )


class TestSource:
    def test_the_original_statements_balance(self):
        assert _statements().balances()


class TestRates:
    def test_the_balance_sheet_uses_the_closing_rate(self):
        result = translate(
            _statements(), "USD", Fraction(12, 10), Fraction(11, 10), Fraction(1)
        )
        assert result.assets == Money.of(1200, "USD")
        assert result.liabilities == Money.of(480, "USD")

    def test_income_uses_the_average_rate(self):
        result = translate(
            _statements(), "USD", Fraction(12, 10), Fraction(11, 10), Fraction(1)
        )
        assert result.revenue == Money.of(880, "USD")
        assert result.expenses == Money.of(770, "USD")
        assert result.net_income() == Money.of(110, "USD")

    def test_equity_uses_the_historical_rate(self):
        result = translate(
            _statements(), "USD", Fraction(12, 10), Fraction(11, 10), Fraction(1)
        )
        assert result.contributed_equity == Money.of(500, "USD")


class TestAdjustment:
    def test_the_residual_makes_it_balance(self):
        result = translate(
            _statements(), "USD", Fraction(12, 10), Fraction(11, 10), Fraction(1)
        )
        assert result.balances()

    def test_the_adjustment_is_the_measured_difference(self):
        result = translate(
            _statements(), "USD", Fraction(12, 10), Fraction(11, 10), Fraction(1)
        )
        # assets 1200 less liabilities 480 less equity 600 = 120.
        assert result.translation_adjustment == Money.of(120, "USD")

    def test_an_unmoved_rate_leaves_no_adjustment(self):
        result = translate(
            _statements(), "USD", Fraction(1), Fraction(1), Fraction(1)
        )
        assert result.translation_adjustment.is_zero()
        assert result.balances()


class TestRefusals:
    def test_translating_the_group_currency_is_refused(self):
        statements = ForeignStatements(
            assets=Money.of(10, "USD"),
            liabilities=Money.of(4, "USD"),
            contributed_equity=Money.of(5, "USD"),
            retained_earnings=Money.of(1, "USD"),
            revenue=Money.of(8, "USD"),
            expenses=Money.of(7, "USD"),
        )
        with pytest.raises(Refused):
            translate(statements, "USD", Fraction(1), Fraction(1), Fraction(1))

    def test_a_nonpositive_rate_is_refused(self):
        with pytest.raises(Refused):
            translate(_statements(), "USD", Fraction(0), Fraction(1), Fraction(1))

    def test_mixed_currency_statements_are_refused(self):
        with pytest.raises(Refused):
            ForeignStatements(
                assets=Money.of(1000, "EUR"),
                liabilities=Money.of(400, "USD"),
                contributed_equity=Money.of(500, "EUR"),
                retained_earnings=Money.of(100, "EUR"),
                revenue=Money.of(800, "EUR"),
                expenses=Money.of(700, "EUR"),
            )
