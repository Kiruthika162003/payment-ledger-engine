"""The gateway: turning payment events into balanced ledger entries.

The modules below the gateway model payment concepts in isolation,
a charge, a refund, a fee, a payout, and the gateway is where each
of those becomes an actual double-entry that keeps the books
balanced. It holds a book and the handful of account roles a
processor needs: a clearing account for money the processor holds
before it pays out, revenue for what was earned, a refunds account
that reduces net revenue, a fees expense, and the bank the payout
lands in. A capture debits clearing and credits revenue; a refund
debits refunds and credits clearing, drawing down the money still
held; a fee debits the expense and credits clearing; a payout moves
the clearing balance to the bank. Because every one of these is a
balanced entry, the book stays in balance across the whole
lifecycle, which is the property the assay measures. The gateway
also carries an idempotency store, so a capture retried under the
same key posts once rather than twice, wiring the double-post
guard into the path where a dropped response is most likely and
most expensive.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.book import Book
from mint.idempotency import IdempotencyStore, fingerprint
from mint.money import Money
from mint.refund import Charge


@dataclass(frozen=True)
class GatewayAccounts:
    clearing: str
    bank: str
    revenue: str
    refunds: str
    fees: str


@dataclass
class Gateway:
    book: Book
    accounts: GatewayAccounts
    idempotency: IdempotencyStore

    def capture(
        self, amount: Money, on: datetime.date, ref: str, key: str | None = None
    ) -> Charge:
        def produce() -> Charge:
            self.book.post(
                self.book.transaction(on, "capture", ref)
                .debit(self.accounts.clearing, amount)
                .credit(self.accounts.revenue, amount)
            )
            return Charge(ref, amount, on)

        if key is None:
            return produce()
        return self.idempotency.execute(
            key, fingerprint("capture", amount.units, amount.currency, ref), produce
        )

    def refund(self, charge: Charge, amount: Money, on: datetime.date, reason: str) -> Money:
        charge.refund(amount, on, reason)
        self.book.post(
            self.book.transaction(on, "refund", charge.id)
            .debit(self.accounts.refunds, amount)
            .credit(self.accounts.clearing, amount)
        )
        return charge.refundable()

    def charge_fee(
        self, amount: Money, on: datetime.date, memo: str = "processing fee"
    ) -> None:
        self.book.post(
            self.book.transaction(on, memo)
            .debit(self.accounts.fees, amount)
            .credit(self.accounts.clearing, amount)
        )

    def payout(self, on: datetime.date) -> Money:
        held = self.book.balance(self.accounts.clearing)
        if not held.is_positive():
            return held
        self.book.post(
            self.book.transaction(on, "payout")
            .debit(self.accounts.bank, held)
            .credit(self.accounts.clearing, held)
        )
        return held

    def net_revenue(self) -> Money:
        # Refunds is a contra-revenue account, debited when money goes back,
        # so its signed income balance is already negative; add it.
        revenue = self.book.balance(self.accounts.revenue)
        refunds = self.book.balance(self.accounts.refunds)
        return revenue + refunds
