from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.revenuecontract import Obligation, RevenueContract

START = datetime.date(2026, 1, 1)


def _contract(price: str = "1000.00") -> RevenueContract:
    contract = RevenueContract("C-1", Money.of(price, "USD"), START)
    contract.add(Obligation("device", Money.of(600, "USD")))
    contract.add(Obligation("service", Money.of(500, "USD"), over_time=True))
    contract.add(Obligation("installation", Money.of(100, "USD")))
    return contract


class TestAllocation:
    def test_the_price_splits_on_standalone_prices(self):
        contract = _contract()
        allocated = contract.allocate_price()
        # Standalone total is 1200; the device takes 600/1200 of 1000.
        assert allocated["device"] == Money.of(500, "USD")
        assert allocated["installation"] == Money.from_minor(8333, "USD")

    def test_the_allocation_sums_to_the_contract(self):
        contract = _contract()
        contract.allocate_price()
        assert contract.allocation_sums_to_price()

    def test_an_awkward_price_still_sums(self):
        contract = _contract("999.99")
        contract.allocate_price()
        assert contract.allocation_sums_to_price()

    def test_a_discounted_bundle_spreads_the_discount(self):
        contract = _contract()
        contract.allocate_price()
        # Every obligation is allocated below its standalone price.
        for obligation in contract.obligations:
            assert obligation.allocated < obligation.standalone_price

    def test_a_contract_with_no_obligations_is_refused(self):
        empty = RevenueContract("C-2", Money.of(100, "USD"), START)
        with pytest.raises(Refused):
            empty.allocate_price()


class TestRecognition:
    def test_nothing_is_recognized_before_satisfaction(self):
        contract = _contract()
        contract.allocate_price()
        assert contract.recognized_revenue().is_zero()

    def test_satisfying_an_obligation_recognizes_its_share(self):
        contract = _contract()
        contract.allocate_price()
        contract.satisfy("device", Fraction(1))
        assert contract.recognized_revenue() == Money.of(500, "USD")

    def test_partial_satisfaction_recognizes_partly(self):
        # Service is allocated 416.67; half of it is 208.335, which half-even
        # rounds up to the even 208.34 rather than down to 208.33.
        contract = _contract()
        contract.allocate_price()
        contract.satisfy("service", Fraction(1, 2))
        assert contract.get("service").recognized() == Money.from_minor(20834, "USD")

    def test_revenue_is_not_reversed_by_a_lower_estimate(self):
        contract = _contract()
        contract.allocate_price()
        contract.satisfy("service", Fraction(1, 2))
        with pytest.raises(Refused) as caught:
            contract.satisfy("service", Fraction(1, 4))
        assert "not reversed" in str(caught.value)

    def test_a_complete_contract_is_reported(self):
        contract = _contract()
        contract.allocate_price()
        for obligation in contract.obligations:
            contract.satisfy(obligation.name, Fraction(1))
        assert contract.is_complete()
        assert contract.recognized_revenue() == Money.of(1000, "USD")


class TestLiability:
    def test_billing_ahead_creates_a_contract_liability(self):
        contract = _contract()
        contract.allocate_price()
        contract.bill(Money.of(1000, "USD"))
        assert contract.contract_liability() == Money.of(1000, "USD")

    def test_recognizing_reduces_the_liability(self):
        contract = _contract()
        contract.allocate_price()
        contract.bill(Money.of(1000, "USD"))
        contract.satisfy("device", Fraction(1))
        assert contract.contract_liability() == Money.of(500, "USD")

    def test_working_ahead_creates_a_contract_asset(self):
        contract = _contract()
        contract.allocate_price()
        contract.satisfy("device", Fraction(1))
        assert contract.contract_asset() == Money.of(500, "USD")
        assert contract.contract_liability().is_zero()

    def test_billing_past_the_contract_is_refused(self):
        contract = _contract()
        contract.allocate_price()
        with pytest.raises(Refused) as caught:
            contract.bill(Money.of(2000, "USD"))
        assert "past the" in str(caught.value)


class TestRefusals:
    def test_a_wrong_currency_obligation_is_refused(self):
        contract = _contract()
        with pytest.raises(Refused):
            contract.add(Obligation("euro", Money.of(1, "EUR")))

    def test_a_duplicate_obligation_is_refused(self):
        contract = _contract()
        with pytest.raises(Refused):
            contract.add(Obligation("device", Money.of(1, "USD")))

    def test_an_unknown_obligation_is_refused(self):
        with pytest.raises(Refused):
            _contract().get("ghost")

    def test_satisfaction_beyond_one_is_refused(self):
        contract = _contract()
        contract.allocate_price()
        with pytest.raises(Refused):
            contract.satisfy("device", Fraction(2))

    def test_recognizing_before_allocation_is_refused(self):
        contract = _contract()
        with pytest.raises(Refused):
            contract.get("device").recognized()
