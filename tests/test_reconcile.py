from __future__ import annotations

import datetime

from mint.money import Money
from mint.reconcile import Movement, reconcile

JAN1 = datetime.date(2026, 1, 1)
JAN2 = datetime.date(2026, 1, 2)
JAN4 = datetime.date(2026, 1, 4)
JAN9 = datetime.date(2026, 1, 9)


def _m(day, amount, ref):
    return Movement(day, Money.of(amount, "USD"), ref)


class TestExactMatch:
    def test_amount_and_ref_match_pairs_them(self):
        ledger = [_m(JAN1, 100, "INV-1")]
        bank = [_m(JAN1, 100, "INV-1")]
        result = reconcile(ledger, bank)
        assert result.is_reconciled()
        assert result.matched_count() == 1

    def test_a_ref_mismatch_falls_to_the_window_pass(self):
        ledger = [_m(JAN1, 100, "INV-1")]
        bank = [_m(JAN2, 100, "DEPOSIT")]
        result = reconcile(ledger, bank)
        assert result.matched_count() == 1


class TestWindow:
    def test_a_payment_clears_a_few_days_later(self):
        ledger = [_m(JAN1, 100, "X")]
        bank = [_m(JAN4, 100, "Y")]
        result = reconcile(ledger, bank, window_days=3)
        assert result.is_reconciled()

    def test_outside_the_window_stays_unmatched(self):
        ledger = [_m(JAN1, 100, "X")]
        bank = [_m(JAN9, 100, "Y")]
        result = reconcile(ledger, bank, window_days=3)
        assert not result.is_reconciled()
        assert len(result.unmatched_ledger) == 1
        assert len(result.unmatched_bank) == 1

    def test_the_nearest_date_wins_among_candidates(self):
        ledger = [_m(JAN2, 100, "X")]
        bank = [_m(JAN4, 100, "far"), _m(JAN1, 100, "near")]
        result = reconcile(ledger, bank, window_days=5)
        matched_bank = result.matched[0][1]
        assert matched_bank.ref == "near"


class TestUnmatched:
    def test_a_missing_deposit_is_named_not_hidden(self):
        ledger = [_m(JAN1, 100, "A"), _m(JAN1, 50, "B")]
        bank = [_m(JAN1, 100, "A")]
        result = reconcile(ledger, bank)
        assert [m.ref for m in result.unmatched_ledger] == ["B"]

    def test_a_cent_gap_does_not_match(self):
        ledger = [_m(JAN1, "100.00", "A")]
        bank = [_m(JAN1, "100.01", "A")]
        result = reconcile(ledger, bank)
        assert not result.is_reconciled()
