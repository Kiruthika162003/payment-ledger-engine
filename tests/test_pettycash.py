from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.pettycash import PettyCash

DAY = datetime.date(2026, 2, 1)


def _tin() -> PettyCash:
    return PettyCash(
        float_amount=Money.of(200, "USD"), cash_on_hand=Money.of(200, "USD")
    )


class TestImprest:
    def test_a_fresh_tin_balances(self):
        assert _tin().is_balanced()

    def test_spending_leaves_a_voucher_that_keeps_it_balanced(self):
        tin = _tin()
        tin.spend("v1", Money.of(35, "USD"), DAY, "taxi", "alice")
        assert tin.cash_on_hand == Money.of(165, "USD")
        assert tin.voucher_total() == Money.of(35, "USD")
        assert tin.is_balanced()

    def test_several_payments_still_add_up(self):
        tin = _tin()
        tin.spend("v1", Money.of(35, "USD"), DAY, "taxi", "alice")
        tin.spend("v2", Money.of("12.50", "USD"), DAY, "stamps", "alice")
        assert tin.accounted_for() == Money.of(200, "USD")
        assert tin.is_balanced()


class TestShortage:
    def test_a_count_that_falls_short_shows_the_variance(self):
        tin = _tin()
        tin.spend("v1", Money.of(35, "USD"), DAY, "taxi", "alice")
        variance = tin.count_cash(Money.of(160, "USD"))
        assert variance == Money.of("-5.00", "USD")
        assert tin.is_short()

    def test_a_count_that_matches_leaves_no_variance(self):
        tin = _tin()
        tin.spend("v1", Money.of(35, "USD"), DAY, "taxi", "alice")
        assert tin.count_cash(Money.of(165, "USD")).is_zero()

    def test_a_negative_count_is_refused(self):
        with pytest.raises(Refused):
            _tin().count_cash(Money.of("-1.00", "USD"))


class TestReimbursement:
    def test_reimbursing_restores_the_float(self):
        tin = _tin()
        tin.spend("v1", Money.of(35, "USD"), DAY, "taxi", "alice")
        tin.spend("v2", Money.of(15, "USD"), DAY, "milk", "alice")
        assert tin.reimbursement_due() == Money.of(50, "USD")
        assert tin.reimburse() == Money.of(50, "USD")
        assert tin.cash_on_hand == Money.of(200, "USD")
        assert tin.is_balanced()

    def test_reimbursing_nothing_is_refused(self):
        with pytest.raises(Refused):
            _tin().reimburse()


class TestSpendGuards:
    def test_spending_more_than_the_tin_holds_is_refused(self):
        with pytest.raises(Refused):
            _tin().spend("v1", Money.of(500, "USD"), DAY, "impossible", "alice")

    def test_a_voucher_needs_a_purpose(self):
        with pytest.raises(Refused):
            _tin().spend("v1", Money.of(10, "USD"), DAY, "  ", "alice")

    def test_a_voucher_needs_an_approver(self):
        with pytest.raises(Refused):
            _tin().spend("v1", Money.of(10, "USD"), DAY, "taxi", "  ")

    def test_a_duplicate_voucher_is_refused(self):
        tin = _tin()
        tin.spend("v1", Money.of(10, "USD"), DAY, "taxi", "alice")
        with pytest.raises(Refused):
            tin.spend("v1", Money.of(10, "USD"), DAY, "taxi again", "alice")


class TestFloatChanges:
    def test_raising_the_float_adds_cash_and_stays_balanced(self):
        tin = _tin()
        tin.change_float(Money.of(300, "USD"), DAY, "more petty spending")
        assert tin.cash_on_hand == Money.of(300, "USD")
        assert tin.is_balanced()

    def test_a_float_change_is_recorded(self):
        tin = _tin()
        tin.change_float(Money.of(300, "USD"), DAY, "more petty spending")
        assert tin.float_changes[-1][2] == "more petty spending"

    def test_a_float_change_needs_a_reason(self):
        with pytest.raises(Refused) as caught:
            _tin().change_float(Money.of(300, "USD"), DAY, "  ")
        assert "confused with a shortage" in str(caught.value)

    def test_a_nonpositive_float_is_refused(self):
        with pytest.raises(Refused):
            _tin().change_float(Money.zero("USD"), DAY, "closing the tin")
