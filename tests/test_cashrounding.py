from __future__ import annotations

import pytest

from mint.cashrounding import round_to_increment, rounding_adjustment, tender
from mint.errors import Refused
from mint.money import Money


class TestSwissFrancs:
    def test_it_rounds_to_the_nearest_five_centimes(self):
        result = tender(Money.of("10.02", "CHF"))
        assert result.tendered == Money.of("10.00", "CHF")
        assert result.difference == Money.of("-0.02", "CHF")

    def test_it_rounds_up_past_the_midpoint(self):
        result = tender(Money.of("10.03", "CHF"))
        assert result.tendered == Money.of("10.05", "CHF")
        assert result.rounds_up()

    def test_an_exact_multiple_is_unchanged(self):
        result = tender(Money.of("10.05", "CHF"))
        assert result.is_exact()

    def test_the_invoice_itself_is_untouched(self):
        result = tender(Money.of("10.02", "CHF"))
        assert result.invoiced == Money.of("10.02", "CHF")


class TestSingleUnitCurrencies:
    def test_a_dollar_rounds_to_itself(self):
        result = tender(Money.of("10.02", "USD"))
        assert result.is_exact()
        assert result.tendered == result.invoiced

    def test_yen_round_to_themselves(self):
        assert tender(Money.of("1000", "JPY")).is_exact()


class TestIncrement:
    def test_rounding_to_an_arbitrary_increment(self):
        assert round_to_increment(Money.of("10.02", "USD"), 5) == Money.of("10.00", "USD")

    def test_a_zero_increment_is_refused(self):
        with pytest.raises(Refused):
            round_to_increment(Money.of(10, "USD"), 0)


class TestTillSession:
    def test_the_session_adjustment_sums_the_differences(self):
        amounts = [
            Money.of("10.02", "CHF"),
            Money.of("10.03", "CHF"),
            Money.of("10.05", "CHF"),
        ]
        # Down two centimes, up two centimes, exact: net zero.
        assert rounding_adjustment(amounts, "CHF").is_zero()

    def test_a_session_that_loses_reports_the_loss(self):
        amounts = [Money.of("10.02", "CHF"), Money.of("20.01", "CHF")]
        assert rounding_adjustment(amounts, "CHF") == Money.of("-0.03", "CHF")

    def test_a_mixed_currency_session_is_refused(self):
        with pytest.raises(Refused):
            rounding_adjustment([Money.of("10.02", "USD")], "CHF")
