from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.gateway import Gateway, GatewayAccounts
from mint.idempotency import IdempotencyStore
from mint.money import Money

DAY = datetime.date(2026, 1, 1)


def _gateway() -> Gateway:
    book = Book()
    book.open("1000", "Clearing", AccountType.ASSET, "USD")
    book.open("1100", "Bank", AccountType.ASSET, "USD")
    book.open("4000", "Revenue", AccountType.INCOME, "USD")
    book.open("4900", "Refunds", AccountType.INCOME, "USD")
    book.open("5000", "Fees", AccountType.EXPENSE, "USD")
    accounts = GatewayAccounts("1000", "1100", "4000", "4900", "5000")
    return Gateway(book, accounts, IdempotencyStore())


class TestLifecycle:
    def test_capture_moves_clearing_and_revenue(self):
        gw = _gateway()
        gw.capture(Money.of(100, "USD"), DAY, "ch_1")
        assert gw.book.balance("1000") == Money.of(100, "USD")
        assert gw.book.balance("4000") == Money.of(100, "USD")

    def test_refund_draws_down_clearing(self):
        gw = _gateway()
        charge = gw.capture(Money.of(100, "USD"), DAY, "ch_1")
        gw.refund(charge, Money.of(30, "USD"), DAY, "return")
        assert gw.book.balance("1000") == Money.of(70, "USD")
        assert gw.net_revenue() == Money.of(70, "USD")

    def test_a_fee_and_payout_settle_the_clearing(self):
        gw = _gateway()
        gw.capture(Money.of(100, "USD"), DAY, "ch_1")
        gw.charge_fee(Money.of(3, "USD"), DAY)
        gw.payout(DAY)
        assert gw.book.balance("1000").is_zero()
        assert gw.book.balance("1100") == Money.of(97, "USD")

    def test_the_book_stays_balanced_across_the_lifecycle(self):
        gw = _gateway()
        charge = gw.capture(Money.of(100, "USD"), DAY, "ch_1")
        gw.charge_fee(Money.of(3, "USD"), DAY)
        gw.refund(charge, Money.of(20, "USD"), DAY, "partial")
        gw.payout(DAY)
        assert gw.book.is_balanced()


class TestIdempotency:
    def test_a_retried_capture_posts_once(self):
        gw = _gateway()
        gw.capture(Money.of(50, "USD"), DAY, "ch_1", key="k1")
        gw.capture(Money.of(50, "USD"), DAY, "ch_1", key="k1")
        assert gw.book.balance("4000") == Money.of(50, "USD")
        assert gw.book.ledger.entry_count() == 1
