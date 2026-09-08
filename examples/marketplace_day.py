"""A marketplace day: split a buyer's payment, hold a reserve, pay the sellers.

This example runs a day on a marketplace that collects one payment
per order and owes several sellers plus itself. It splits each
order between the sellers and the platform commission, withholds a
rolling reserve against future refunds, refunds part of one order
and claws back the commission proportionally, and posts the whole
lot to a ledger that stays balanced throughout. It composes the
marketplace split, the rolling reserve, and the gateway with the
double-entry core, and every printed line is pinned in the suite.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.accounts import AccountType
from mint.book import Book
from mint.gateway import Gateway, GatewayAccounts
from mint.idempotency import IdempotencyStore
from mint.marketplace import SellerLine, split_payment, split_refund
from mint.money import Money
from mint.reserve import RollingReserve

DAY = datetime.date(2026, 9, 1)
RELEASE_DAY = datetime.date(2026, 12, 1)


def _dollars(money: Money) -> str:
    return money.format(with_symbol=False)


def _gateway() -> Gateway:
    book = Book()
    book.open("1000", "Clearing", AccountType.ASSET, "USD")
    book.open("1100", "Bank", AccountType.ASSET, "USD")
    book.open("4000", "Commission Revenue", AccountType.INCOME, "USD")
    book.open("4900", "Refunds", AccountType.INCOME, "USD")
    book.open("5000", "Processing Fees", AccountType.EXPENSE, "USD")
    accounts = GatewayAccounts("1000", "1100", "4000", "4900", "5000")
    return Gateway(book, accounts, IdempotencyStore())


def run() -> list[str]:
    lines = ["Marketplace, one day"]

    order = split_payment(
        Money.of(100, "USD"),
        [
            SellerLine("baker", Money.of(60, "USD"), Fraction(10, 100)),
            SellerLine("florist", Money.of(40, "USD"), Fraction(15, 100)),
        ],
    )
    lines.append(f"Buyer paid: {_dollars(order.payment)}")
    for share in order.shares:
        lines.append(
            f"  {share.seller_id} nets {_dollars(share.net)} "
            f"after {_dollars(share.commission)} commission"
        )
    lines.append(f"Platform commission: {_dollars(order.platform)}")
    lines.append(f"Split reconciles: {order.reconciles()}")

    reserve = RollingReserve(rate=Fraction(10, 100), hold_days=90, currency="USD")
    withholding = reserve.withhold("s1", Money.of(100, "USD"), DAY)
    lines.append(f"Reserve withheld: {_dollars(withholding.withheld)}")
    lines.append(f"Paid out today: {_dollars(reserve.payout_for('s1'))}")
    lines.append(f"Reserve releases on: {withholding.releases_on.isoformat()}")

    back = split_refund(order, "baker", Money.of(30, "USD"))
    lines.append(
        f"Refunded {_dollars(back.gross)} to a buyer; "
        f"commission clawed back {_dollars(back.commission)}"
    )

    gateway = _gateway()
    charge = gateway.capture(Money.of(100, "USD"), DAY, "order-1", key="idem-1")
    gateway.capture(Money.of(100, "USD"), DAY, "order-1", key="idem-1")
    lines.append(f"Retried capture posted once: {gateway.book.ledger.entry_count() == 1}")
    gateway.charge_fee(Money.of("2.90", "USD"), DAY)
    gateway.refund(charge, Money.of(30, "USD"), DAY, "buyer returned an item")
    paid_out = gateway.payout(DAY)
    lines.append(f"Payout to bank: {_dollars(paid_out)}")
    lines.append(f"Net revenue: {_dollars(gateway.net_revenue())}")
    lines.append(f"Books balanced: {gateway.book.is_balanced()}")

    released = reserve.release(RELEASE_DAY)
    lines.append(f"Reserve released later: {_dollars(released)}")
    lines.append(f"Reserve balance after: {_dollars(reserve.balance(RELEASE_DAY))}")
    return lines


def main() -> None:
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
