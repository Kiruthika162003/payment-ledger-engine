from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.purchaseorder import PurchaseOrder


def _order() -> PurchaseOrder:
    order = PurchaseOrder("PO-1", "USD")
    order.add_line("widget", 100, Money.of(5, "USD"))
    order.add_line("gadget", 20, Money.of(50, "USD"))
    return order


class TestCleanMatch:
    def test_a_matching_order_is_payable(self):
        order = _order()
        order.receive("widget", 100)
        order.bill("widget", 100)
        order.receive("gadget", 20)
        order.bill("gadget", 20)
        assert order.is_payable()
        assert order.fully_received()

    def test_the_ordered_total_extends_the_lines(self):
        assert _order().ordered_total() == Money.of(1500, "USD")


class TestMismatches:
    def test_billing_more_than_ordered_is_caught(self):
        order = _order()
        order.receive("widget", 100)
        order.bill("widget", 120)
        comparisons = {finding.comparison for finding in order.match()}
        assert "billed against ordered" in comparisons

    def test_billing_more_than_received_is_caught(self):
        order = _order()
        order.receive("widget", 50)
        order.bill("widget", 100)
        comparisons = {finding.comparison for finding in order.match()}
        assert "billed against received" in comparisons

    def test_over_delivery_is_caught(self):
        order = _order()
        order.receive("widget", 130)
        comparisons = {finding.comparison for finding in order.match()}
        assert "received against ordered" in comparisons

    def test_the_finding_names_the_line(self):
        order = _order()
        order.receive("widget", 50)
        order.bill("widget", 100)
        assert all(f.sku == "widget" for f in order.match())

    def test_findings_explain_what_they_mean(self):
        order = _order()
        order.receive("widget", 50)
        order.bill("widget", 100)
        detail = " ".join(f.detail for f in order.match())
        assert "in transit" in detail


class TestTolerance:
    def test_a_small_shortfall_passes_within_tolerance(self):
        order = PurchaseOrder("PO-2", "USD")
        order.add_line("widget", 100, Money.of(5, "USD"))
        order.receive("widget", 98)
        order.bill("widget", 100)
        assert order.is_payable(tolerance=Fraction(5, 100))

    def test_the_same_shortfall_fails_without_tolerance(self):
        order = PurchaseOrder("PO-2", "USD")
        order.add_line("widget", 100, Money.of(5, "USD"))
        order.receive("widget", 98)
        order.bill("widget", 100)
        assert not order.is_payable()

    def test_a_tolerance_of_one_is_refused(self):
        with pytest.raises(Refused):
            _order().match(tolerance=Fraction(1))


class TestRefusals:
    def test_a_duplicate_line_is_refused(self):
        order = _order()
        with pytest.raises(Refused):
            order.add_line("widget", 5, Money.of(5, "USD"))

    def test_receiving_an_unordered_sku_is_refused(self):
        with pytest.raises(Refused):
            _order().receive("ghost", 1)

    def test_a_wrong_currency_line_is_refused(self):
        with pytest.raises(Refused):
            _order().add_line("euro-part", 1, Money.of(5, "EUR"))
