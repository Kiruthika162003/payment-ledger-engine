from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.taxprovision import TaxProvision


def _provision(**kwargs) -> TaxProvision:
    base = {
        "currency": "USD",
        "profit_before_tax": Money.of(1000000, "USD"),
        "statutory_rate": Fraction(25, 100),
        "current_tax": Money.of(200000, "USD"),
        "deferred_tax": Money.of(30000, "USD"),
    }
    base.update(kwargs)
    return TaxProvision(**base)


class TestStartingPoint:
    def test_tax_at_the_statutory_rate(self):
        assert _provision().tax_at_statutory_rate() == Money.of(250000, "USD")

    def test_the_total_charge_is_current_plus_deferred(self):
        assert _provision().total_charge() == Money.of(230000, "USD")


class TestReconciliation:
    def test_an_unexplained_gap_is_reported(self):
        provision = _provision()
        assert provision.unexplained() == Money.of("-20000.00", "USD")
        assert not provision.reconciles()

    def test_naming_the_items_makes_it_foot(self):
        provision = _provision()
        provision.add("income not taxed", Money.of("-25000.00", "USD"))
        provision.add("expenses not allowed", Money.of(5000, "USD"))
        assert provision.reconciles()

    def test_a_walk_that_does_not_foot_is_refused(self):
        with pytest.raises(Refused) as caught:
            _provision().walk()
        assert "plug line called other" in str(caught.value)

    def test_the_walk_lists_every_step(self):
        provision = _provision()
        provision.add("income not taxed", Money.of("-20000.00", "USD"))
        rows = provision.walk()
        assert rows[0][0] == "tax at the statutory rate"
        assert rows[-1] == ("total tax charge", 23000000)

    def test_closing_with_an_item_names_the_gap(self):
        provision = _provision()
        item = provision.close_with_item("prior year adjustment")
        assert item.tax_effect == Money.of("-20000.00", "USD")
        assert provision.reconciles()

    def test_closing_a_footed_walk_is_refused(self):
        provision = _provision()
        provision.close_with_item("adjustment")
        with pytest.raises(Refused):
            provision.close_with_item("again")


class TestRates:
    def test_the_effective_rate_is_below_the_statutory_here(self):
        provision = _provision()
        assert provision.effective_rate() == Fraction(23, 100)
        assert provision.effective_rate() < provision.statutory_rate

    def test_no_effective_rate_without_profit(self):
        provision = _provision(profit_before_tax=Money.zero("USD"))
        assert provision.effective_rate() is None

    def test_a_mostly_deferred_charge_is_named(self):
        provision = _provision(
            current_tax=Money.of(10000, "USD"), deferred_tax=Money.of(200000, "USD")
        )
        assert provision.is_mostly_deferred()

    def test_a_mostly_current_charge_is_not(self):
        assert not _provision().is_mostly_deferred()

    def test_no_share_without_a_charge(self):
        provision = _provision(
            current_tax=Money.zero("USD"), deferred_tax=Money.zero("USD")
        )
        assert provision.current_share() is None


class TestRefusals:
    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            _provision(statutory_rate=Fraction(1))

    def test_an_unnamed_item_is_refused(self):
        with pytest.raises(Refused):
            _provision().add("  ", Money.of(1, "USD"))

    def test_a_wrong_currency_item_is_refused(self):
        with pytest.raises(Refused):
            _provision().add("x", Money.of(1, "EUR"))
