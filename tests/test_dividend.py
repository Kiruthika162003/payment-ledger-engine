from __future__ import annotations

import datetime

import pytest

from mint.dividend import DividendState, ShareRegister, declare
from mint.errors import Refused
from mint.money import Money

DECLARED = datetime.date(2026, 3, 1)
RECORD = datetime.date(2026, 3, 15)
PAYMENT = datetime.date(2026, 4, 1)
EARLY = datetime.date(2026, 1, 1)
LATE = datetime.date(2026, 3, 20)


def _register() -> ShareRegister:
    register = ShareRegister()
    register.add("alice", 600, EARLY)
    register.add("bob", 400, EARLY)
    return register


def _dividend(total: str = "1000.00", reserves: str = "5000.00"):
    return declare(
        "D-1",
        Money.of(total, "USD"),
        Money.of(reserves, "USD"),
        DECLARED,
        RECORD,
        PAYMENT,
    )


class TestDeclaration:
    def test_a_dividend_within_reserves_declares(self):
        dividend = _dividend()
        assert dividend.state is DividendState.DECLARED

    def test_a_dividend_beyond_reserves_is_refused(self):
        with pytest.raises(Refused) as caught:
            _dividend(total="9000.00", reserves="5000.00")
        assert "their own capital" in str(caught.value)

    def test_the_shortfall_is_named(self):
        with pytest.raises(Refused) as caught:
            _dividend(total="6000.00", reserves="5000.00")
        assert "1000.00" in str(caught.value)

    def test_it_becomes_a_liability_on_declaration(self):
        dividend = _dividend()
        assert dividend.is_liability_on(DECLARED)
        assert not dividend.is_liability_on(EARLY)


class TestRecordDate:
    def test_holders_on_the_record_date_are_entitled(self):
        register = _register()
        assert len(register.entitled_on(RECORD)) == 2

    def test_a_later_buyer_is_not_entitled(self):
        register = _register()
        register.add("carol", 1000, LATE)
        assert len(register.entitled_on(RECORD)) == 2
        assert register.shares_on(RECORD) == 1000
        assert register.total_shares() == 2000

    def test_the_allocation_follows_the_record_date_holders(self):
        register = _register()
        register.add("carol", 1000, LATE)
        amounts = dict(_dividend().allocate_to(register))
        assert "carol" not in amounts
        assert amounts["alice"] == Money.of(600, "USD")
        assert amounts["bob"] == Money.of(400, "USD")

    def test_the_allocation_conserves_the_cent(self):
        register = ShareRegister()
        register.add("a", 1, EARLY)
        register.add("b", 1, EARLY)
        register.add("c", 1, EARLY)
        amounts = _dividend(total="100.00").allocate_to(register)
        assert sum(amount.units for _, amount in amounts) == 10000

    def test_no_entitled_holder_is_refused(self):
        with pytest.raises(Refused):
            _dividend().allocate_to(ShareRegister())


class TestPayment:
    def test_paying_on_the_date_settles_the_total(self):
        dividend = _dividend()
        assert dividend.pay(_register(), PAYMENT) == Money.of(1000, "USD")
        assert dividend.state is DividendState.PAID

    def test_paying_early_is_refused(self):
        with pytest.raises(Refused) as caught:
            _dividend().pay(_register(), RECORD)
        assert "not before" in str(caught.value)

    def test_paying_twice_is_refused(self):
        dividend = _dividend()
        dividend.pay(_register(), PAYMENT)
        with pytest.raises(Refused):
            dividend.pay(_register(), PAYMENT)

    def test_a_paid_dividend_is_no_longer_a_liability(self):
        dividend = _dividend()
        dividend.pay(_register(), PAYMENT)
        assert not dividend.is_liability_on(PAYMENT)


class TestCancellation:
    def test_a_declared_dividend_can_be_cancelled(self):
        assert _dividend().cancel() is DividendState.CANCELLED

    def test_a_paid_dividend_cannot_be_cancelled(self):
        dividend = _dividend()
        dividend.pay(_register(), PAYMENT)
        with pytest.raises(Refused):
            dividend.cancel()


class TestDates:
    def test_a_record_date_before_declaration_is_refused(self):
        with pytest.raises(Refused):
            declare(
                "D-2",
                Money.of(100, "USD"),
                Money.of(1000, "USD"),
                RECORD,
                DECLARED,
                PAYMENT,
            )

    def test_payment_before_the_record_date_is_refused(self):
        with pytest.raises(Refused):
            declare(
                "D-2",
                Money.of(100, "USD"),
                Money.of(1000, "USD"),
                DECLARED,
                PAYMENT,
                RECORD,
            )
