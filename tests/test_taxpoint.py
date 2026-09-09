from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.taxpoint import Supply, Trigger

SUPPLIED = datetime.date(2026, 4, 10)
EARLY = datetime.date(2026, 3, 15)
SOON_AFTER = datetime.date(2026, 4, 20)
MUCH_LATER = datetime.date(2026, 5, 30)


def _supply(**kwargs) -> Supply:
    base = {
        "id": "S-1",
        "total": Money.of(1000, "USD"),
        "supplied_on": SUPPLIED,
    }
    base.update(kwargs)
    return Supply(**base)


class TestBasicRule:
    def test_without_an_invoice_the_supply_date_rules(self):
        supply = _supply()
        assert supply.actual_tax_point() == SUPPLIED
        assert supply.tax_points()[0].trigger is Trigger.SUPPLY

    def test_the_whole_amount_falls_at_one_point(self):
        supply = _supply()
        points = supply.tax_points()
        assert len(points) == 1
        assert points[0].amount == Money.of(1000, "USD")


class TestInvoiceWindow:
    def test_an_invoice_inside_the_window_moves_the_tax_point(self):
        supply = _supply(invoiced_on=SOON_AFTER)
        assert supply.actual_tax_point() == SOON_AFTER
        assert supply.tax_points()[0].trigger is Trigger.INVOICE_WITHIN_WINDOW

    def test_an_invoice_outside_the_window_does_not(self):
        supply = _supply(invoiced_on=MUCH_LATER)
        assert supply.actual_tax_point() == SUPPLIED

    def test_the_window_length_is_configurable(self):
        supply = _supply(invoiced_on=MUCH_LATER, invoice_window_days=60)
        assert supply.actual_tax_point() == MUCH_LATER

    def test_the_basic_point_is_still_reported(self):
        supply = _supply(invoiced_on=SOON_AFTER)
        assert supply.basic_tax_point() == SUPPLIED


class TestAdvancePayment:
    def test_a_deposit_creates_its_own_earlier_tax_point(self):
        supply = _supply()
        supply.receive_payment(EARLY, Money.of(300, "USD"))
        points = supply.tax_points()
        assert len(points) == 2
        assert points[0].date == EARLY
        assert points[0].trigger is Trigger.PAYMENT_IN_ADVANCE

    def test_the_balance_falls_at_the_supply_date(self):
        supply = _supply()
        supply.receive_payment(EARLY, Money.of(300, "USD"))
        assert supply.tax_points()[1].amount == Money.of(700, "USD")

    def test_one_sale_can_span_two_periods(self):
        supply = _supply()
        supply.receive_payment(EARLY, Money.of(300, "USD"))
        assert supply.spans_two_periods()

    def test_the_amount_in_each_period_is_reported(self):
        supply = _supply()
        supply.receive_payment(EARLY, Money.of(300, "USD"))
        assert supply.amount_in_period(2026, 3) == Money.of(300, "USD")
        assert supply.amount_in_period(2026, 4) == Money.of(700, "USD")

    def test_a_payment_after_supply_moves_nothing(self):
        supply = _supply()
        supply.receive_payment(MUCH_LATER, Money.of(300, "USD"))
        assert not supply.spans_two_periods()
        assert supply.tax_points()[0].date == SUPPLIED

    def test_the_points_always_reconcile_to_the_total(self):
        supply = _supply()
        supply.receive_payment(EARLY, Money.of(300, "USD"))
        supply.receive_payment(EARLY, Money.of(200, "USD"))
        assert supply.points_reconcile()

    def test_a_fully_prepaid_supply_has_only_advance_points(self):
        supply = _supply()
        supply.receive_payment(EARLY, Money.of(1000, "USD"))
        points = supply.tax_points()
        assert len(points) == 1
        assert points[0].trigger is Trigger.PAYMENT_IN_ADVANCE


class TestRefusals:
    def test_over_prepaying_is_refused(self):
        supply = _supply()
        with pytest.raises(Refused):
            supply.receive_payment(EARLY, Money.of(2000, "USD"))

    def test_a_nonpositive_payment_is_refused(self):
        with pytest.raises(Refused):
            _supply().receive_payment(EARLY, Money.zero("USD"))

    def test_a_wrong_currency_payment_is_refused(self):
        with pytest.raises(Refused):
            _supply().receive_payment(EARLY, Money.of(100, "EUR"))

    def test_a_nonpositive_supply_is_refused(self):
        with pytest.raises(Refused):
            _supply(total=Money.zero("USD"))
