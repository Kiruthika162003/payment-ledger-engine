from __future__ import annotations

import datetime

import pytest

from mint.duplicate import (
    PaymentRecord,
    compare,
    normalize_invoice,
    scan,
    strong_candidates,
)
from mint.errors import Refused
from mint.money import Money

JAN1 = datetime.date(2026, 1, 1)
JAN3 = datetime.date(2026, 1, 3)
FEB1 = datetime.date(2026, 2, 1)


def _payment(pid, vendor="Acme", amount="500.00", date=JAN1, invoice="INV-100"):
    return PaymentRecord(pid, vendor, Money.of(amount, "USD"), date, invoice)


class TestNormalization:
    def test_punctuation_and_leading_zeros_are_stripped(self):
        assert normalize_invoice("INV-000123") == normalize_invoice("inv123")

    def test_an_all_zero_number_collapses_to_a_single_zero(self):
        # Stripping per digit-run keeps one zero rather than emptying the
        # field, so 000 and 0 are recognized as the same invoice number.
        assert normalize_invoice("000") == "0"
        assert normalize_invoice("000") == normalize_invoice("0")


class TestComparison:
    def test_an_obvious_duplicate_fires_every_signal(self):
        candidate = compare(_payment("p1"), _payment("p2", date=JAN3))
        assert candidate.score == 4
        assert candidate.is_strong()

    def test_a_different_vendor_lowers_the_score(self):
        candidate = compare(_payment("p1"), _payment("p2", vendor="Other", date=JAN3))
        assert "same vendor" not in candidate.signals

    def test_a_rescanned_invoice_number_still_matches(self):
        left = _payment("p1", invoice="INV-000123")
        right = _payment("p2", invoice="inv123", date=JAN3)
        assert "matching invoice number" in compare(left, right).signals

    def test_the_signals_are_reported_not_just_a_verdict(self):
        candidate = compare(_payment("p1"), _payment("p2", date=JAN3))
        assert len(candidate.signals) == candidate.score


class TestRecurring:
    def test_a_monthly_repeat_is_downgraded(self):
        candidate = compare(_payment("p1"), _payment("p2", date=FEB1), window_days=40)
        assert candidate.likely_recurring
        assert not candidate.is_strong()

    def test_a_few_days_apart_is_not_recurring(self):
        candidate = compare(_payment("p1"), _payment("p2", date=JAN3))
        assert not candidate.likely_recurring


class TestScan:
    def test_a_scan_finds_the_pair(self):
        found = scan([_payment("p1"), _payment("p2", date=JAN3)])
        assert len(found) == 1

    def test_unrelated_payments_are_not_flagged(self):
        payments = [
            _payment("p1"),
            _payment("p2", vendor="Other", amount="123.45", invoice="X-9", date=FEB1),
        ]
        assert scan(payments) == []

    def test_strong_candidates_exclude_recurring(self):
        payments = [_payment("p1"), _payment("p2", date=FEB1)]
        found = scan(payments, window_days=40)
        assert found
        assert strong_candidates(found) == []

    def test_a_zero_threshold_is_refused(self):
        with pytest.raises(Refused) as caught:
            scan([_payment("p1")], minimum_score=0)
        assert "flags every pair" in str(caught.value)
