from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.writeoff import ReceivableAccount, WriteOffPolicy

DAY = datetime.date(2026, 6, 1)


def _account(amount: str = "1000.00") -> ReceivableAccount:
    return ReceivableAccount("c1", Money.of(amount, "USD"))


def _policy() -> WriteOffPolicy:
    return WriteOffPolicy(Money.of(500, "USD"), frozenset({"controller"}))


class TestWriteOff:
    def test_a_write_off_reduces_the_outstanding(self):
        account = _account()
        account.write_off("w1", Money.of(300, "USD"), DAY, "bankrupt", "clerk")
        assert account.outstanding == Money.of(700, "USD")
        assert account.written_off_total() == Money.of(300, "USD")

    def test_writing_off_more_than_is_owed_is_refused(self):
        account = _account()
        with pytest.raises(Refused):
            account.write_off("w1", Money.of(1500, "USD"), DAY, "gone", "clerk")

    def test_a_settled_balance_has_nothing_to_write_off(self):
        account = ReceivableAccount("c1", Money.zero("USD"))
        with pytest.raises(Refused) as caught:
            account.write_off("w1", Money.of(10, "USD"), DAY, "gone", "clerk")
        assert "already settled" in str(caught.value)

    def test_a_write_off_needs_a_reason(self):
        with pytest.raises(Refused) as caught:
            _account().write_off("w1", Money.of(10, "USD"), DAY, "  ", "clerk")
        assert "embezzlement" in str(caught.value)

    def test_a_write_off_needs_an_authorizer(self):
        with pytest.raises(Refused):
            _account().write_off("w1", Money.of(10, "USD"), DAY, "gone", "  ")


class TestPolicy:
    def test_a_large_write_off_needs_a_senior_approver(self):
        account = _account()
        with pytest.raises(Refused) as caught:
            account.write_off(
                "w1", Money.of(600, "USD"), DAY, "gone", "clerk", _policy()
            )
        assert "senior approver" in str(caught.value)

    def test_a_senior_approver_may_exceed_the_threshold(self):
        account = _account()
        item = account.write_off(
            "w1", Money.of(600, "USD"), DAY, "gone", "controller", _policy()
        )
        assert item.amount == Money.of(600, "USD")

    def test_a_small_write_off_passes_without_seniority(self):
        account = _account()
        account.write_off("w1", Money.of(100, "USD"), DAY, "gone", "clerk", _policy())
        assert account.outstanding == Money.of(900, "USD")


class TestRecovery:
    def test_a_recovery_is_recorded_against_its_write_off(self):
        account = _account()
        account.write_off("w1", Money.of(300, "USD"), DAY, "gone", "clerk")
        assert account.recover("w1", Money.of(120, "USD"), DAY) == Money.of(120, "USD")

    def test_recovering_more_than_was_written_off_is_refused(self):
        account = _account()
        account.write_off("w1", Money.of(300, "USD"), DAY, "gone", "clerk")
        with pytest.raises(Refused):
            account.recover("w1", Money.of(400, "USD"), DAY)

    def test_recovering_against_an_unknown_write_off_is_refused(self):
        with pytest.raises(Refused):
            _account().recover("nope", Money.of(10, "USD"), DAY)
