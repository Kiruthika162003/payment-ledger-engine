from __future__ import annotations

import datetime

import pytest

from mint.errors import InsufficientFunds, Refused
from mint.merchantaccount import MerchantAccount
from mint.money import Money

DAY1 = datetime.date(2026, 5, 1)
DAY5 = datetime.date(2026, 5, 5)
DAY10 = datetime.date(2026, 5, 10)


def _account(**kwargs) -> MerchantAccount:
    base = {"merchant_id": "M-1", "currency": "USD"}
    base.update(kwargs)
    return MerchantAccount(**base)


def _trading() -> MerchantAccount:
    account = _account()
    account.sale(Money.of(1000, "USD"), DAY1, "order-1")
    account.fee(Money.of(29, "USD"), DAY1)
    account.refund(Money.of(100, "USD"), DAY1, "order-1")
    return account


class TestBalances:
    def test_gross_sales_are_what_customers_paid(self):
        assert _trading().gross_sales(DAY10) == Money.of(1000, "USD")

    def test_available_is_gross_less_refunds_and_fees(self):
        assert _trading().available_balance(DAY10) == Money.of(871, "USD")

    def test_a_chargeback_reduces_the_available_balance(self):
        account = _trading()
        account.chargeback(Money.of(50, "USD"), DAY5)
        assert account.available_balance(DAY10) == Money.of(821, "USD")

    def test_the_three_balances_differ(self):
        account = _trading()
        account.hold_reserve(Money.of(100, "USD"), DAY1)
        assert account.gross_sales(DAY10) != account.available_balance(DAY10)
        assert account.available_balance(DAY10) != account.payable_balance(DAY10)


class TestUncleared:
    def test_a_fresh_sale_has_not_cleared(self):
        account = _account()
        account.sale(Money.of(500, "USD"), DAY5)
        assert account.uncleared(DAY5) == Money.of(500, "USD")
        assert account.payable_balance(DAY5).is_zero()

    def test_it_clears_after_the_delay(self):
        account = _account()
        account.sale(Money.of(500, "USD"), DAY1)
        assert account.uncleared(DAY10).is_zero()
        assert account.payable_balance(DAY10) == Money.of(500, "USD")

    def test_a_longer_delay_holds_it_longer(self):
        account = _account(settlement_delay_days=30)
        account.sale(Money.of(500, "USD"), DAY1)
        assert account.payable_balance(DAY10).is_zero()


class TestReserve:
    def test_a_reserve_reduces_what_is_payable(self):
        account = _trading()
        account.hold_reserve(Money.of(200, "USD"), DAY1)
        assert account.reserve_balance(DAY10) == Money.of(200, "USD")
        assert account.payable_balance(DAY10) == Money.of(671, "USD")

    def test_releasing_it_frees_the_money(self):
        account = _trading()
        account.hold_reserve(Money.of(200, "USD"), DAY1)
        account.release_reserve(Money.of(200, "USD"), DAY5)
        assert account.reserve_balance(DAY10).is_zero()
        assert account.payable_balance(DAY10) == Money.of(871, "USD")


class TestPayout:
    def test_a_payout_takes_the_payable_balance(self):
        account = _trading()
        assert account.pay_out(DAY10) == Money.of(871, "USD")
        assert account.payable_balance(DAY10).is_zero()

    def test_paying_out_nothing_is_refused(self):
        account = _account()
        with pytest.raises(InsufficientFunds) as caught:
            account.pay_out(DAY10)
        assert "not payable" in str(caught.value)

    def test_a_statement_lists_every_line(self):
        account = _trading()
        rows = dict(account.statement(DAY10))
        assert rows["gross sales"] == 100000
        assert rows["payable now"] == 87100
        assert "held in reserve" in rows


class TestRefusals:
    def test_a_wrong_currency_movement_is_refused(self):
        with pytest.raises(Refused):
            _account().sale(Money.of(10, "EUR"), DAY1)

    def test_a_nonpositive_movement_is_refused(self):
        with pytest.raises(Refused):
            _account().fee(Money.zero("USD"), DAY1)

    def test_balances_can_be_read_as_of_a_past_day(self):
        account = _trading()
        account.sale(Money.of(500, "USD"), DAY10)
        assert account.gross_sales(DAY5) == Money.of(1000, "USD")
