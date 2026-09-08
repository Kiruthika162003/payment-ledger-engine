from __future__ import annotations

from fractions import Fraction

import pytest

from mint.eps import Convertible, EarningsPerShare, ShareTranche
from mint.errors import Refused
from mint.money import Money


def _eps(income: str = "1000000.00") -> EarningsPerShare:
    calculation = EarningsPerShare(net_income=Money.of(income, "USD"))
    calculation.add_tranche(1000000, Fraction(1))
    return calculation


class TestWeighting:
    def test_a_full_year_tranche_counts_in_full(self):
        assert _eps().weighted_average_shares() == Fraction(1000000)

    def test_a_mid_year_issue_counts_partly(self):
        calculation = _eps()
        calculation.add_tranche(400000, Fraction(1, 2))
        assert calculation.weighted_average_shares() == Fraction(1200000)

    def test_the_closing_count_would_have_overstated_the_denominator(self):
        calculation = _eps()
        calculation.add_tranche(400000, Fraction(1, 2))
        assert calculation.weighted_average_shares() < Fraction(1400000)

    def test_a_buyback_reduces_the_weighted_average(self):
        calculation = _eps()
        calculation.add_tranche(-200000, Fraction(1, 2))
        assert calculation.weighted_average_shares() == Fraction(900000)

    def test_a_zero_tranche_is_refused(self):
        with pytest.raises(Refused):
            ShareTranche(0, Fraction(1))

    def test_an_impossible_fraction_is_refused(self):
        with pytest.raises(Refused):
            ShareTranche(100, Fraction(2))


class TestBasic:
    def test_basic_earnings_per_share(self):
        # 100,000,000 cents over 1,000,000 shares is 100 cents.
        assert _eps().basic() == Fraction(100)

    def test_no_shares_leaves_it_undefined(self):
        calculation = EarningsPerShare(net_income=Money.of(1000, "USD"))
        assert calculation.basic() is None


class TestDilution:
    def test_a_dilutive_instrument_lowers_the_figure(self):
        calculation = _eps()
        calculation.add_instrument(
            Convertible("options", 200000, Money.zero("USD"))
        )
        assert calculation.diluted() < calculation.basic()
        assert calculation.is_diluted()

    def test_an_antidilutive_instrument_is_excluded(self):
        calculation = _eps()
        # Adds far more earnings than shares, so it would improve the figure.
        calculation.add_instrument(
            Convertible("rich convertible", 1000, Money.of(500000, "USD"))
        )
        assert calculation.diluted() == calculation.basic()
        assert len(calculation.antidilutive_instruments()) == 1

    def test_the_excluded_instruments_are_named(self):
        calculation = _eps()
        calculation.add_instrument(
            Convertible("rich convertible", 1000, Money.of(500000, "USD"))
        )
        assert calculation.antidilutive_instruments()[0].name == "rich convertible"

    def test_dilutive_instruments_are_listed(self):
        calculation = _eps()
        calculation.add_instrument(Convertible("options", 200000, Money.zero("USD")))
        assert len(calculation.dilutive_instruments()) == 1

    def test_the_dilution_effect_is_reported(self):
        calculation = _eps()
        calculation.add_instrument(Convertible("options", 200000, Money.zero("USD")))
        effect = calculation.dilution_effect()
        assert effect is not None
        assert effect > 0

    def test_no_instruments_means_no_dilution(self):
        assert not _eps().is_diluted()

    def test_an_instrument_converting_to_nothing_is_refused(self):
        with pytest.raises(Refused):
            Convertible("empty", 0, Money.zero("USD"))

    def test_a_wrong_currency_instrument_is_refused(self):
        with pytest.raises(Refused):
            _eps().add_instrument(Convertible("euro", 100, Money.of(1, "EUR")))
