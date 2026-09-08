from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.remittance import OpenInvoice, RemittanceAdvice


def _invoices():
    return [
        OpenInvoice("INV-1", Money.of(500, "USD")),
        OpenInvoice("INV-2", Money.of(300, "USD")),
    ]


def _advice(cash: str) -> RemittanceAdvice:
    return RemittanceAdvice(payer="acme", currency="USD", cash_received=Money.of(cash, "USD"))


class TestCleanApplication:
    def test_an_exact_advice_applies_cleanly(self):
        advice = _advice("800.00")
        advice.add("INV-1", Money.of(500, "USD"))
        advice.add("INV-2", Money.of(300, "USD"))
        result = advice.apply(_invoices())
        assert result.is_clean()
        assert result.total_applied() == Money.of(800, "USD")

    def test_the_advice_total_is_reported(self):
        advice = _advice("800.00")
        advice.add("INV-1", Money.of(500, "USD"))
        advice.add("INV-2", Money.of(300, "USD"))
        assert advice.advice_total() == Money.of(800, "USD")
        assert advice.matches_cash()


class TestShortPay:
    def test_a_short_pay_applies_and_reports_the_deduction(self):
        advice = _advice("750.00")
        advice.add("INV-1", Money.of(450, "USD"))
        advice.add("INV-2", Money.of(300, "USD"))
        result = advice.apply(_invoices())
        short = result.short_pays()
        assert len(short) == 1
        assert short[0].invoice_id == "INV-1"
        assert short[0].deduction == Money.of(50, "USD")

    def test_a_short_pay_is_not_clean(self):
        advice = _advice("750.00")
        advice.add("INV-1", Money.of(450, "USD"))
        advice.add("INV-2", Money.of(300, "USD"))
        assert not advice.apply(_invoices()).is_clean()


class TestUnknownAndOver:
    def test_an_unknown_reference_is_not_applied(self):
        advice = _advice("900.00")
        advice.add("INV-1", Money.of(500, "USD"))
        advice.add("INV-9", Money.of(400, "USD"))
        result = advice.apply(_invoices())
        assert result.unknown_references == ("INV-9",)
        assert result.unapplied == Money.of(400, "USD")

    def test_an_overpayment_applies_only_the_balance(self):
        advice = _advice("900.00")
        advice.add("INV-1", Money.of(600, "USD"))
        advice.add("INV-2", Money.of(300, "USD"))
        result = advice.apply(_invoices())
        assert result.overpaid == ("INV-1",)
        assert result.unapplied == Money.of(100, "USD")

    def test_the_applied_total_excludes_the_unapplied(self):
        advice = _advice("900.00")
        advice.add("INV-1", Money.of(500, "USD"))
        advice.add("INV-9", Money.of(400, "USD"))
        result = advice.apply(_invoices())
        assert result.total_applied() == Money.of(500, "USD")


class TestCashMismatch:
    def test_an_advice_that_does_not_match_the_cash_is_refused(self):
        advice = _advice("700.00")
        advice.add("INV-1", Money.of(500, "USD"))
        advice.add("INV-2", Money.of(300, "USD"))
        with pytest.raises(Refused) as caught:
            advice.apply(_invoices())
        assert "out of step with the bank" in str(caught.value)

    def test_matches_cash_reports_the_mismatch(self):
        advice = _advice("700.00")
        advice.add("INV-1", Money.of(500, "USD"))
        assert not advice.matches_cash()


class TestRefusals:
    def test_a_wrong_currency_line_is_refused(self):
        with pytest.raises(Refused):
            _advice("100.00").add("INV-1", Money.of(100, "EUR"))

    def test_a_nonpositive_line_is_refused(self):
        with pytest.raises(Refused):
            _advice("100.00").add("INV-1", Money.zero("USD"))
