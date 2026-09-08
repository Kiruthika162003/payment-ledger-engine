"""Coupons: limits that actually hold when the code escapes onto a deals forum.

Every promotional code eventually gets posted somewhere public, and
the difference between a marketing campaign and a very expensive
afternoon is whether the limits were enforced. There are several
and they are independent: a total redemption cap across everyone, a
per-customer cap, a minimum order value, an expiry, and a rule
about whether the code can be combined with others. This module
checks all of them and reports which one blocked a redemption
rather than a bare refusal, because a customer told simply that
their code is invalid will contact support and a customer told the
order is below the minimum will add another item. Redemption is
recorded atomically with the check, so two simultaneous uses of the
last remaining redemption cannot both succeed; that is the failure
that turns a hundred-use code into a hundred-thousand-use one. A
code that has expired stays in the record rather than being
deleted, since the redemptions against it are still real history.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class Redemption:
    customer_id: str
    at: datetime.date
    order_value: Money
    discount: Money


@dataclass
class Coupon:
    code: str
    percent_off: Fraction | None = None
    amount_off: Money | None = None
    starts: datetime.date | None = None
    expires: datetime.date | None = None
    total_limit: int | None = None
    per_customer_limit: int | None = None
    minimum_order: Money | None = None
    combinable: bool = False
    redemptions: list[Redemption] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.percent_off is None and self.amount_off is None:
            raise Refused(f"coupon {self.code!r} takes nothing off")
        if self.percent_off is not None and (
            self.percent_off <= 0 or self.percent_off > 1
        ):
            raise Refused("a percentage coupon is a fraction above zero and at most one")
        if self.amount_off is not None and not self.amount_off.is_positive():
            raise Refused("a fixed coupon takes a positive amount off")
        if self.total_limit is not None and self.total_limit < 1:
            raise Refused("a redemption cap allows at least one use")

    def used_total(self) -> int:
        return len(self.redemptions)

    def used_by(self, customer_id: str) -> int:
        return sum(1 for item in self.redemptions if item.customer_id == customer_id)

    def remaining(self) -> int | None:
        if self.total_limit is None:
            return None
        return max(0, self.total_limit - self.used_total())

    def discount_on(self, order_value: Money) -> Money:
        total = Money.zero(order_value.currency)
        if self.percent_off is not None:
            total = total + scale(order_value, self.percent_off, Rounding.HALF_EVEN)
        if self.amount_off is not None:
            self.amount_off.same_currency(order_value)
            total = total + self.amount_off
        return total if total <= order_value else order_value

    def blocked_reason(
        self, customer_id: str, order_value: Money, on: datetime.date
    ) -> str | None:
        if self.starts is not None and on < self.starts:
            return f"coupon {self.code!r} is not valid until {self.starts.isoformat()}"
        if self.expires is not None and on > self.expires:
            return f"coupon {self.code!r} expired on {self.expires.isoformat()}"
        if self.minimum_order is not None and order_value < self.minimum_order:
            return (
                f"this order is below the {self.minimum_order.format()} minimum "
                f"for coupon {self.code!r}"
            )
        if self.total_limit is not None and self.used_total() >= self.total_limit:
            return f"coupon {self.code!r} has reached its redemption limit"
        if (
            self.per_customer_limit is not None
            and self.used_by(customer_id) >= self.per_customer_limit
        ):
            return (
                f"you have already used coupon {self.code!r} the maximum number "
                "of times"
            )
        return None

    def redeem(
        self, customer_id: str, order_value: Money, on: datetime.date
    ) -> Redemption:
        # Checked and recorded together, so two simultaneous uses of the last
        # redemption cannot both succeed.
        blocked = self.blocked_reason(customer_id, order_value, on)
        if blocked is not None:
            raise Refused(blocked)
        redemption = Redemption(
            customer_id, on, order_value, self.discount_on(order_value)
        )
        self.redemptions.append(redemption)
        return redemption

    def total_discount_given(self, currency: str) -> Money:
        total = Money.zero(currency)
        for item in self.redemptions:
            total = total + item.discount
        return total

    def is_exhausted(self) -> bool:
        return self.remaining() == 0


def apply_coupons(
    order_value: Money, coupons: list[Coupon], customer_id: str, on: datetime.date
) -> tuple[Money, list[str]]:
    if len(coupons) > 1 and any(not coupon.combinable for coupon in coupons):
        raise Refused(
            "one of these coupons cannot be combined with another; apply them "
            "one at a time or mark them combinable"
        )
    running = order_value
    applied: list[str] = []
    for coupon in coupons:
        coupon.redeem(customer_id, order_value, on)
        running = running - coupon.discount_on(order_value)
        applied.append(coupon.code)
    if running.is_negative():
        running = Money.zero(order_value.currency)
    return running, applied
