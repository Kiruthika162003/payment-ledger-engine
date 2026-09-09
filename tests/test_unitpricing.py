from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.unitpricing import UnitFund, UnitHolding


def _fund(**kwargs) -> UnitFund:
    base = {
        "name": "growth",
        "currency": "USD",
        "net_assets": Money.of(100000, "USD"),
        "units_issued": Fraction(100000),
    }
    base.update(kwargs)
    fund = UnitFund(**base)
    fund.holdings["alice"] = Fraction(60000)
    fund.holdings["bob"] = Fraction(40000)
    return fund


class TestPricing:
    def test_the_price_is_net_assets_over_units(self):
        fund = _fund()
        assert fund.exact_price() == Fraction(100)

    def test_the_price_is_exact_not_rounded(self):
        fund = _fund(net_assets=Money.of(100001, "USD"))
        assert fund.exact_price() == Fraction(10000100, 100000)

    def test_the_quoted_price_is_rounded_for_publication(self):
        fund = _fund(net_assets=Money.of("100000.03", "USD"), price_places=2)
        assert fund.quoted_price() == Fraction(100, 1)

    def test_a_fund_with_no_units_cannot_be_priced(self):
        fund = UnitFund("seed", "USD", Money.of(10, "USD"), Fraction(0))
        with pytest.raises(Refused) as caught:
            fund.exact_price()
        assert "nothing to divide" in str(caught.value)

    def test_a_fund_with_no_assets_cannot_be_priced(self):
        fund = UnitFund("empty", "USD", Money.zero("USD"), Fraction(100))
        with pytest.raises(Refused):
            fund.exact_price()


class TestDealing:
    def test_an_issue_buys_units_at_the_exact_price(self):
        fund = _fund()
        dealing = fund.issue("carol", Money.of(1000, "USD"))
        assert dealing.units == Fraction(1000)
        assert fund.units_issued == Fraction(101000)

    def test_the_price_is_unchanged_by_a_fair_issue(self):
        fund = _fund()
        before = fund.exact_price()
        fund.issue("carol", Money.of(1000, "USD"))
        assert fund.exact_price() == before

    def test_a_redemption_returns_the_holders_value(self):
        fund = _fund()
        dealing = fund.redeem("bob", Fraction(40000))
        assert dealing.consideration == Money.of(40000, "USD")
        assert "bob" not in fund.holdings

    def test_redeeming_more_than_held_is_refused(self):
        fund = _fund()
        with pytest.raises(Refused) as caught:
            fund.redeem("bob", Fraction(50000))
        assert "does not lend units" in str(caught.value)

    def test_a_partial_redemption_leaves_the_remainder(self):
        fund = _fund()
        fund.redeem("alice", Fraction(10000))
        assert fund.holdings["alice"] == Fraction(50000)

    def test_a_negative_investment_is_refused(self):
        with pytest.raises(Refused):
            _fund().units_for(Money.of("-1.00", "USD"))


class TestDilutionLevy:
    def test_the_levy_reduces_the_units_bought(self):
        plain = _fund()
        levied = _fund(dilution_levy_rate=Fraction(1, 100))
        assert levied.units_for(Money.of(1000, "USD")) < plain.units_for(
            Money.of(1000, "USD")
        )

    def test_the_levy_stays_in_the_fund_and_lifts_the_price(self):
        fund = _fund(dilution_levy_rate=Fraction(1, 100))
        before = fund.exact_price()
        fund.issue("carol", Money.of(1000, "USD"))
        assert fund.exact_price() > before

    def test_no_levy_means_no_charge(self):
        assert _fund().levy_on(Money.of(1000, "USD")).is_zero()

    def test_a_negative_levy_rate_is_refused(self):
        with pytest.raises(Refused):
            _fund(dilution_levy_rate=Fraction(-1, 100))


class TestReporting:
    def test_a_holders_value_is_their_share_of_the_assets(self):
        fund = _fund()
        assert fund.value_of("alice") == Money.of(60000, "USD")
        assert fund.value_of("nobody").is_zero()

    def test_the_holdings_sum_to_the_units_issued(self):
        fund = _fund()
        assert fund.units_held() == fund.units_issued
        assert fund.unattributed_units() == Fraction(0)

    def test_seed_units_show_as_unattributed(self):
        fund = _fund(units_issued=Fraction(110000))
        assert fund.unattributed_units() == Fraction(10000)

    def test_revaluing_moves_the_price(self):
        fund = _fund()
        assert fund.revalue(Money.of(110000, "USD")) == Fraction(110)

    def test_the_rounding_drift_is_reported_not_hidden(self):
        fund = _fund(net_assets=Money.of("100000.03", "USD"), price_places=2)
        # Guessed the drift would be zero; measured 3 cents, because the
        # published price of 100.00 cannot express the extra three cents
        # spread across a hundred thousand units.
        assert fund.rounding_drift() == Money.of("-0.03", "USD")

    def test_a_matched_price_has_no_drift(self):
        assert _fund().rounding_drift().is_zero()

    def test_the_holders_are_listed_in_order(self):
        assert _fund().holders() == ("alice", "bob")


class TestConstruction:
    def test_a_currency_mismatch_is_refused(self):
        with pytest.raises(Refused):
            UnitFund("odd", "USD", Money.of(100, "EUR"), Fraction(100))

    def test_negative_units_are_refused(self):
        with pytest.raises(Refused):
            UnitFund("odd", "USD", Money.of(100, "USD"), Fraction(-1))

    def test_a_holding_needs_positive_units(self):
        with pytest.raises(Refused):
            UnitHolding("alice", Fraction(0))

    def test_negative_price_places_are_refused(self):
        with pytest.raises(Refused):
            _fund(price_places=-1)
