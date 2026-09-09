"""Layaway: the customer pays over time and the goods stay on the shelf until they finish.

Layaway inverts the usual credit arrangement. Instead of taking the
goods and paying later, the customer pays first and collects only
when the balance is clear, which means the retailer never carries
credit risk and the customer never carries debt. The accounting
follows from that: the payments are a liability, a deposit held
against a future sale, not revenue, and the goods stay in inventory
because they have not been sold. A retailer that books layaway
payments as revenue reports profit on sales that may never
complete, and then has to unwind it when a customer walks away. The
cancellation rules are the other half. A customer who abandons a
plan is usually refunded less a cancellation fee, and the fee is
capped, since keeping a large deposit for goods that went back on
the shelf is the practice consumer rules exist to limit. Only on
the final payment does the sale happen and the deposit turn into
revenue.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


class LayawayState(Enum):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FORFEITED = "forfeited"


@dataclass
class LayawayPlan:
    id: str
    price: Money
    started: datetime.date
    deadline: datetime.date
    cancellation_rate: Fraction = Fraction(10, 100)
    cancellation_cap: Money | None = None
    payments: list[tuple[datetime.date, Money]] = field(default_factory=list)
    state: LayawayState = LayawayState.OPEN
    closed_on: datetime.date | None = None

    def __post_init__(self) -> None:
        if not self.price.is_positive():
            raise Refused("a layaway plan is for a positive price")
        if self.deadline <= self.started:
            raise Refused("a layaway deadline falls after it starts")
        if self.cancellation_rate < 0 or self.cancellation_rate >= 1:
            raise Refused("a cancellation fee is a fraction below one")
        if self.cancellation_cap is not None:
            self.cancellation_cap.same_currency(self.price)

    def paid(self) -> Money:
        total = Money.zero(self.price.currency)
        for _, amount in self.payments:
            total = total + amount
        return total

    def outstanding(self) -> Money:
        return self.price - self.paid()

    def deposit_liability(self) -> Money:
        # A liability while the plan is open: the sale has not happened.
        if self.state is LayawayState.OPEN:
            return self.paid()
        return Money.zero(self.price.currency)

    def revenue_recognized(self) -> Money:
        if self.state is LayawayState.COMPLETED:
            return self.price
        return Money.zero(self.price.currency)

    def goods_still_in_inventory(self) -> bool:
        return self.state is not LayawayState.COMPLETED

    def pay(self, amount: Money, on: datetime.date) -> Money:
        amount.same_currency(self.price)
        if self.state is not LayawayState.OPEN:
            raise Refused(f"plan {self.id!r} is {self.state.value}")
        if not amount.is_positive():
            raise Refused("a layaway payment is a positive amount")
        if amount > self.outstanding():
            raise Refused(
                f"a payment of {amount.format()} exceeds the "
                f"{self.outstanding().format()} still owed on plan {self.id!r}"
            )
        if on > self.deadline:
            raise Refused(
                f"plan {self.id!r} passed its deadline on "
                f"{self.deadline.isoformat()}; it must be reinstated first"
            )
        self.payments.append((on, amount))
        if self.outstanding().is_zero():
            # Only now is there a sale.
            self.state = LayawayState.COMPLETED
        return self.outstanding()

    def cancellation_fee(self) -> Money:
        fee = scale(self.price, self.cancellation_rate, Rounding.HALF_EVEN)
        if self.cancellation_cap is not None and fee > self.cancellation_cap:
            fee = self.cancellation_cap
        return fee if fee <= self.paid() else self.paid()

    def cancel(self, on: datetime.date) -> Money:
        if self.state is not LayawayState.OPEN:
            raise Refused(f"plan {self.id!r} is {self.state.value}")
        refund = self.paid() - self.cancellation_fee()
        self.state = LayawayState.CANCELLED
        self.closed_on = on
        return refund

    def forfeit(self, on: datetime.date) -> Money:
        if self.state is not LayawayState.OPEN:
            raise Refused(f"plan {self.id!r} is {self.state.value}")
        if on <= self.deadline:
            raise Refused(
                f"plan {self.id!r} has not passed its deadline of "
                f"{self.deadline.isoformat()} and cannot be forfeited"
            )
        self.state = LayawayState.FORFEITED
        self.closed_on = on
        return self.paid()

    def is_complete(self) -> bool:
        return self.state is LayawayState.COMPLETED

    def progress(self) -> Fraction:
        return Fraction(self.paid().units, self.price.units)
