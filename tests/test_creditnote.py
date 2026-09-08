from __future__ import annotations

import datetime

import pytest

from mint.creditnote import CreditedInvoice
from mint.errors import Refused
from mint.money import Money

ISSUED = datetime.date(2026, 2, 1)
LATER = datetime.date(2026, 2, 10)


def _invoice(amount: str = "1000.00") -> CreditedInvoice:
    return CreditedInvoice("INV-1", Money.of(amount, "USD"), ISSUED)


class TestIssuing:
    def test_a_credit_reduces_what_is_owed(self):
        invoice = _invoice()
        invoice.issue("CN-1", Money.of(200, "USD"), LATER, "damaged goods")
        assert invoice.net_owed() == Money.of(800, "USD")

    def test_credits_accumulate_to_full(self):
        invoice = _invoice()
        invoice.issue("CN-1", Money.of(600, "USD"), LATER, "return")
        invoice.issue("CN-2", Money.of(400, "USD"), LATER, "the rest")
        assert invoice.is_fully_credited()
        assert invoice.credited_total() == Money.of(1000, "USD")

    def test_cancel_credits_everything_left(self):
        invoice = _invoice()
        invoice.issue("CN-1", Money.of(250, "USD"), LATER, "partial")
        note = invoice.cancel("CN-2", LATER, "order cancelled")
        assert note.amount == Money.of(750, "USD")
        assert invoice.is_fully_credited()


class TestRefusals:
    def test_crediting_beyond_the_invoice_is_refused(self):
        invoice = _invoice()
        with pytest.raises(Refused) as caught:
            invoice.issue("CN-1", Money.of(1200, "USD"), LATER, "too much")
        assert "beyond the invoice is a payment" in str(caught.value)

    def test_a_credit_needs_a_reason(self):
        with pytest.raises(Refused) as caught:
            _invoice().issue("CN-1", Money.of(10, "USD"), LATER, "  ")
        assert "auditor stops on" in str(caught.value)

    def test_a_credit_predating_the_invoice_is_refused(self):
        with pytest.raises(Refused):
            _invoice().issue("CN-1", Money.of(10, "USD"), datetime.date(2026, 1, 1), "early")

    def test_a_nonpositive_credit_is_refused(self):
        with pytest.raises(Refused):
            _invoice().issue("CN-1", Money.zero("USD"), LATER, "nothing")

    def test_a_nonpositive_invoice_is_refused(self):
        with pytest.raises(Refused):
            CreditedInvoice("INV-X", Money.zero("USD"), ISSUED)
