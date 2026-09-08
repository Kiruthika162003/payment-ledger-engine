from __future__ import annotations

from fractions import Fraction

import pytest

from mint.discount import Discount
from mint.errors import Refused
from mint.invoice import Invoice
from mint.money import Money
from mint.tax import TaxLine


def _invoice() -> Invoice:
    invoice = Invoice("USD")
    invoice.add_line("Widget", 3, Money.of(10, "USD"))
    invoice.add_line("Gadget", 2, Money.of("12.50", "USD"))
    return invoice


class TestArithmetic:
    def test_the_subtotal_extends_each_line(self):
        assert _invoice().subtotal() == Money.of(55, "USD")

    def test_tax_follows_discount(self):
        invoice = _invoice()
        invoice.discounts.append(Discount.of_percent(Fraction(1, 10), "10%"))
        invoice.taxes.append(TaxLine("state", Fraction(8, 100)))
        # subtotal 55, less 10% = 49.50, tax 8% on 49.50 = 3.96, total 53.46.
        summary = invoice.summary()
        assert summary["taxable"] == Money.of("49.50", "USD")
        assert summary["tax"] == Money.of("3.96", "USD")
        assert summary["total"] == Money.of("53.46", "USD")

    def test_without_tax_or_discount_total_is_the_subtotal(self):
        assert _invoice().total() == Money.of(55, "USD")


class TestLines:
    def test_a_fractional_quantity_rounds_once(self):
        invoice = Invoice("USD")
        invoice.add_line("Cable", Fraction(1, 3), Money.of(1, "USD"))
        # one third of a dollar rounds to 33 cents, a single rounding.
        assert invoice.subtotal() == Money.from_minor(33, "USD")

    def test_a_wrong_currency_line_is_refused(self):
        with pytest.raises(Refused):
            Invoice("USD").add_line("x", 1, Money.of(1, "EUR"))

    def test_a_nonpositive_quantity_is_refused(self):
        with pytest.raises(Refused):
            Invoice("USD").add_line("x", 0, Money.of(1, "USD"))
