"""Return policy: what comes back, in what condition, and what the customer actually gets.

A return is not simply a reversed sale. The policy decides three
things and each of them changes the refund: whether the return is
inside the window, whether the goods came back in a condition worth
restocking, and whether the original shipping is refunded. Getting
the third wrong is the most common complaint, because a customer
who paid shipping and returns a faulty item expects it back while
one who simply changed their mind usually does not, and a policy
that treats both the same generates a dispute either way. This
module encodes the policy as data and computes the refund from it,
reporting the deductions by name so a customer service agent can
explain the number rather than defend it. A return outside the
window is refused rather than silently refunded at zero, since a
zero refund and a rejected return are different outcomes and the
customer needs to know which one happened.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


class Condition(Enum):
    UNOPENED = "unopened"
    OPENED = "opened"
    DAMAGED = "damaged"
    FAULTY = "faulty"


class Reason(Enum):
    CHANGED_MIND = "changed_mind"
    NOT_AS_DESCRIBED = "not_as_described"
    FAULTY = "faulty"


@dataclass(frozen=True)
class ReturnPolicy:
    window_days: int
    restocking_rate: Fraction = Fraction(0)
    refund_shipping_on_fault: bool = True
    refund_shipping_on_change_of_mind: bool = False
    accept_opened: bool = True
    accept_damaged: bool = False

    def __post_init__(self) -> None:
        if self.window_days < 0:
            raise Refused("a return window is not negative")
        if self.restocking_rate < 0 or self.restocking_rate >= 1:
            raise Refused("a restocking fee is a fraction below one")


@dataclass(frozen=True)
class RefundQuote:
    goods: Money
    restocking_fee: Money
    shipping_refunded: Money
    total: Money
    deductions: tuple[tuple[str, int], ...]

    def reconciles(self) -> bool:
        return self.goods - self.restocking_fee + self.shipping_refunded == self.total


def quote_refund(
    policy: ReturnPolicy,
    price: Money,
    shipping_paid: Money,
    purchased_on: datetime.date,
    returned_on: datetime.date,
    condition: Condition,
    reason: Reason,
) -> RefundQuote:
    shipping_paid.same_currency(price)
    if returned_on < purchased_on:
        raise Refused("a return cannot predate the purchase")
    days = (returned_on - purchased_on).days
    at_fault = reason in (Reason.FAULTY, Reason.NOT_AS_DESCRIBED)

    if days > policy.window_days and not at_fault:
        raise Refused(
            f"the return window of {policy.window_days} days closed "
            f"{days - policy.window_days} days ago; a rejected return is not "
            "the same as a refund of nothing"
        )
    if condition is Condition.DAMAGED and not policy.accept_damaged and not at_fault:
        raise Refused(
            "goods returned damaged are not accepted under this policy unless "
            "the fault was ours"
        )
    if condition is Condition.OPENED and not policy.accept_opened and not at_fault:
        raise Refused("opened goods are not accepted under this policy")

    deductions: list[tuple[str, int]] = []
    fee = Money.zero(price.currency)
    if not at_fault and policy.restocking_rate > 0 and condition is not Condition.UNOPENED:
        fee = scale(price, policy.restocking_rate, Rounding.HALF_EVEN)
        deductions.append(("restocking fee", fee.units))

    if at_fault:
        shipping = shipping_paid if policy.refund_shipping_on_fault else Money.zero(
            price.currency
        )
    else:
        shipping = (
            shipping_paid
            if policy.refund_shipping_on_change_of_mind
            else Money.zero(price.currency)
        )
    if shipping.is_zero() and shipping_paid.is_positive():
        deductions.append(("shipping not refunded", shipping_paid.units))

    return RefundQuote(
        goods=price,
        restocking_fee=fee,
        shipping_refunded=shipping,
        total=price - fee + shipping,
        deductions=tuple(deductions),
    )


def within_window(
    policy: ReturnPolicy, purchased_on: datetime.date, returned_on: datetime.date
) -> bool:
    return 0 <= (returned_on - purchased_on).days <= policy.window_days


def standard_policy() -> ReturnPolicy:
    return ReturnPolicy(
        window_days=30,
        restocking_rate=Fraction(15, 100),
        refund_shipping_on_fault=True,
        refund_shipping_on_change_of_mind=False,
        accept_opened=True,
        accept_damaged=False,
    )
