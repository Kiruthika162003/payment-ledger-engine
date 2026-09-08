from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.interestposting import InterestAccount
from mint.money import Money

OPENED = datetime.date(2026, 1, 1)
JAN31 = datetime.date(2026, 1, 31)
FEB28 = datetime.date(2026, 2, 28)


def _account(**kwargs) -> InterestAccount:
    base = {
        "id": "S-1",
        "balance": Money.of(10000, "USD"),
        "annual_rate": Fraction(365, 10000),
        "opened": OPENED,
    }
    base.update(kwargs)
    return InterestAccount(**base)


class TestAccrual:
    def test_interest_accrues_daily(self):
        account = _account()
        posting = account.post_interest(JAN31)
        # 30 days at 3.65% annual on 10000 is 30.00.
        assert posting.interest == Money.of(30, "USD")
        assert posting.days == 30

    def test_a_zero_balance_earns_nothing(self):
        account = _account(balance=Money.zero("USD"))
        assert account.post_interest(JAN31).interest.is_zero()

    def test_a_mid_period_deposit_earns_only_from_then(self):
        quiet = _account()
        active = _account()
        active.deposit(Money.of(10000, "USD"), datetime.date(2026, 1, 16))
        assert active.post_interest(JAN31).interest > quiet.post_interest(JAN31).interest


class TestIdempotence:
    def test_posting_again_for_the_same_days_pays_nothing(self):
        account = _account()
        first = account.post_interest(JAN31)
        second = account.post_interest(JAN31)
        assert first.interest == Money.of(30, "USD")
        assert second.interest.is_zero()
        assert second.days == 0

    def test_posting_backward_is_refused(self):
        account = _account()
        account.post_interest(JAN31)
        with pytest.raises(Refused) as caught:
            account.post_interest(datetime.date(2026, 1, 15))
        assert "days already paid" in str(caught.value)

    def test_a_later_run_covers_only_the_new_days(self):
        account = _account()
        account.post_interest(JAN31)
        second = account.post_interest(FEB28)
        assert second.days == 28


class TestCapitalizing:
    def test_posted_interest_joins_the_balance(self):
        account = _account()
        account.post_interest(JAN31)
        assert account.balance_on(JAN31) == Money.of(10030, "USD")

    def test_capitalized_interest_earns_afterward(self):
        account = _account()
        account.post_interest(JAN31)
        second = account.post_interest(FEB28)
        # 28 days on 10030 earns more than 28 days on 10000 would.
        plain = _account()
        plain.post_interest(FEB28)
        assert second.interest.is_positive()
        assert account.total_interest_posted() > plain.total_interest_posted()


class TestMovements:
    def test_withdrawals_reduce_the_balance(self):
        account = _account()
        account.withdraw(Money.of(4000, "USD"), datetime.date(2026, 1, 10))
        assert account.balance_on(JAN31) == Money.of(6000, "USD")

    def test_overdrawing_is_refused(self):
        with pytest.raises(Refused):
            _account().withdraw(Money.of(20000, "USD"), JAN31)

    def test_a_wrong_currency_movement_is_refused(self):
        with pytest.raises(Refused):
            _account().deposit(Money.of(10, "EUR"), JAN31)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            _account(annual_rate=Fraction(-1, 100))
