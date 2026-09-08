from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.milestone import MilestoneContract
from mint.money import Money

DAY = datetime.date(2026, 5, 1)


def _contract(**kwargs) -> MilestoneContract:
    base = {"id": "C-1", "contract_value": Money.of(100000, "USD")}
    base.update(kwargs)
    contract = MilestoneContract(**base)
    contract.define([("design", 2), ("build", 5), ("handover", 3)])
    return contract


class TestDefinition:
    def test_the_stages_sum_to_the_contract(self):
        assert _contract().milestones_sum_to_contract()

    def test_weights_decide_the_amounts(self):
        contract = _contract()
        assert contract.get("design").amount == Money.of(20000, "USD")
        assert contract.get("build").amount == Money.of(50000, "USD")

    def test_an_awkward_value_still_sums(self):
        contract = MilestoneContract("C-2", Money.of("1000.00", "USD"))
        contract.define([("a", 1), ("b", 1), ("c", 1)])
        assert contract.milestones_sum_to_contract()

    def test_an_empty_definition_is_refused(self):
        with pytest.raises(Refused):
            MilestoneContract("C-3", Money.of(100, "USD")).define([])

    def test_a_zero_weight_is_refused(self):
        with pytest.raises(Refused):
            MilestoneContract("C-3", Money.of(100, "USD")).define([("a", 0)])


class TestInvoicing:
    def test_an_accepted_stage_invoices(self):
        contract = _contract()
        contract.accept("design", DAY)
        assert contract.invoice("design") == Money.of(20000, "USD")

    def test_an_unaccepted_stage_cannot_bill(self):
        contract = _contract()
        with pytest.raises(Refused) as caught:
            contract.invoice("design")
        assert "not before" in str(caught.value)

    def test_a_stage_bills_once(self):
        contract = _contract()
        contract.accept("design", DAY)
        contract.invoice("design")
        with pytest.raises(Refused):
            contract.invoice("design")

    def test_accepting_twice_is_refused(self):
        contract = _contract()
        contract.accept("design", DAY)
        with pytest.raises(Refused):
            contract.accept("design", DAY)

    def test_the_total_never_exceeds_the_contract(self):
        contract = _contract()
        for name in ("design", "build", "handover"):
            contract.accept(name, DAY)
            contract.invoice(name)
        assert contract.invoiced_total() == Money.of(100000, "USD")
        assert contract.never_exceeds_contract()


class TestRetention:
    def test_retention_is_withheld_from_what_is_payable(self):
        contract = _contract(retention_rate=Fraction(5, 100))
        contract.accept("design", DAY)
        contract.invoice("design")
        assert contract.invoiced_total() == Money.of(20000, "USD")
        assert contract.retained_total() == Money.of(1000, "USD")
        assert contract.payable_now() == Money.of(19000, "USD")

    def test_retention_releases_only_when_complete(self):
        contract = _contract(retention_rate=Fraction(5, 100))
        contract.accept("design", DAY)
        contract.invoice("design")
        with pytest.raises(Refused) as caught:
            contract.release_retention()
        assert "not before" in str(caught.value)

    def test_a_completed_contract_releases_retention(self):
        contract = _contract(retention_rate=Fraction(5, 100))
        for name in ("design", "build", "handover"):
            contract.accept(name, DAY)
            contract.invoice(name)
        assert contract.is_complete()
        assert contract.release_retention() == Money.of(5000, "USD")

    def test_a_retention_rate_of_one_is_refused(self):
        with pytest.raises(Refused):
            MilestoneContract("C", Money.of(100, "USD"), retention_rate=Fraction(1))
