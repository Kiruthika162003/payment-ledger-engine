"""Dividends: paid only out of profits that exist, and only to holders on the record date.

A dividend is a distribution of profit, and the constraint that
makes it lawful rather than a return of capital is that it comes
out of distributable reserves, the accumulated profits actually
available. A company that pays a dividend it has not earned is
handing shareholders their own capital back and, in most places,
the directors are personally on the hook for it. So this module
checks the reserves before declaring and refuses a dividend that
exceeds them, naming the shortfall. The dates are the other half.
A dividend has a declaration date, when the obligation comes into
existence and becomes a liability, a record date, which fixes who
is entitled, and a payment date. Shares bought after the record
date do not carry the dividend, which is why the price drops on
the ex-dividend date, and a system that pays on the current holder
list rather than the record-date list pays the wrong people. The
per-share amount is allocated with the cent conserved so the total
paid equals the total declared exactly.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused
from mint.money import Money
from mint.rounding import allocate


class DividendState(Enum):
    DECLARED = "declared"
    PAID = "paid"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Holding:
    holder: str
    shares: int
    held_from: datetime.date

    def __post_init__(self) -> None:
        if self.shares < 1:
            raise Refused("a holding is at least one share")


@dataclass
class ShareRegister:
    holdings: list[Holding] = field(default_factory=list)

    def add(self, holder: str, shares: int, held_from: datetime.date) -> Holding:
        holding = Holding(holder, shares, held_from)
        self.holdings.append(holding)
        return holding

    def entitled_on(self, record_date: datetime.date) -> list[Holding]:
        # Shares acquired after the record date do not carry the dividend.
        return sorted(
            (h for h in self.holdings if h.held_from <= record_date),
            key=lambda h: h.holder,
        )

    def shares_on(self, record_date: datetime.date) -> int:
        return sum(h.shares for h in self.entitled_on(record_date))

    def total_shares(self) -> int:
        return sum(h.shares for h in self.holdings)


@dataclass
class Dividend:
    id: str
    total: Money
    declared_on: datetime.date
    record_date: datetime.date
    payment_date: datetime.date
    state: DividendState = DividendState.DECLARED

    def __post_init__(self) -> None:
        if not self.total.is_positive():
            raise Refused("a dividend distributes a positive amount")
        if self.record_date < self.declared_on:
            raise Refused("a record date cannot precede the declaration")
        if self.payment_date < self.record_date:
            raise Refused("a dividend is paid on or after its record date")

    def is_liability_on(self, as_of: datetime.date) -> bool:
        # It becomes an obligation the moment it is declared, not when paid.
        return (
            self.state is DividendState.DECLARED
            and as_of >= self.declared_on
        )

    def allocate_to(self, register: ShareRegister) -> list[tuple[str, Money]]:
        entitled = register.entitled_on(self.record_date)
        if not entitled:
            raise Refused(
                f"no holder qualifies on the record date "
                f"{self.record_date.isoformat()}"
            )
        shares = [holding.shares for holding in entitled]
        amounts = allocate(self.total, shares)
        return [
            (holding.holder, amount)
            for holding, amount in zip(entitled, amounts, strict=True)
        ]

    def pay(self, register: ShareRegister, on: datetime.date) -> Money:
        if self.state is not DividendState.DECLARED:
            raise Refused(f"dividend {self.id!r} is {self.state.value}")
        if on < self.payment_date:
            raise Refused(
                f"dividend {self.id!r} is payable on "
                f"{self.payment_date.isoformat()}, not before"
            )
        paid = Money.zero(self.total.currency)
        for _, amount in self.allocate_to(register):
            paid = paid + amount
        self.state = DividendState.PAID
        return paid

    def cancel(self) -> DividendState:
        if self.state is DividendState.PAID:
            raise Refused(f"dividend {self.id!r} has been paid and cannot be cancelled")
        self.state = DividendState.CANCELLED
        return self.state


def declare(
    dividend_id: str,
    total: Money,
    distributable_reserves: Money,
    declared_on: datetime.date,
    record_date: datetime.date,
    payment_date: datetime.date,
) -> Dividend:
    total.same_currency(distributable_reserves)
    if total > distributable_reserves:
        shortfall = total - distributable_reserves
        raise Refused(
            f"a dividend of {total.format()} exceeds distributable reserves of "
            f"{distributable_reserves.format()} by {shortfall.format()}; paying "
            "it would return shareholders their own capital"
        )
    return Dividend(dividend_id, total, declared_on, record_date, payment_date)
