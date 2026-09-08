"""Subscription metrics: recurring revenue, churn, and the movements between them.

Recurring revenue is the one number a subscription business is
judged on, and it is easy to compute wrongly in a way that
flatters. Monthly recurring revenue is the normalized monthly value
of active subscriptions, so an annual plan contributes a twelfth of
its price each month rather than its whole price in the month it
was billed, and a business that books the annual payment as one
month's revenue shows a spike it did not earn. This module
normalizes by billing interval before summing. The movement
between two months is decomposed the way an investor reads it: new
revenue from new customers, expansion from existing customers
paying more, contraction from those paying less, and churn from
those who left, and the four must reconcile exactly to the change
in total, which is the identity the tests hold to. Churn rate is
computed against the opening base rather than the closing one,
because dividing by the closing base flatters a shrinking month,
and the module refuses to compute a rate on an empty base rather
than returning a zero that reads as perfect retention.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class Subscription:
    customer_id: str
    amount: Money
    months_per_period: int

    def __post_init__(self) -> None:
        if self.months_per_period < 1:
            raise Refused("a billing period spans at least one month")
        if not self.amount.is_positive():
            raise Refused("a subscription is for a positive amount")

    def monthly_value(self) -> Money:
        return round_money(
            Fraction(self.amount.units, self.months_per_period),
            self.amount.currency,
            Rounding.HALF_EVEN,
        )


@dataclass(frozen=True)
class RevenueMovement:
    new: Money
    expansion: Money
    contraction: Money
    churn: Money
    opening: Money
    closing: Money

    def net_change(self) -> Money:
        return self.new + self.expansion - self.contraction - self.churn

    def reconciles(self) -> bool:
        return self.opening + self.net_change() == self.closing

    def churn_rate(self) -> Fraction | None:
        if self.opening.units == 0:
            return None
        return Fraction(self.churn.units, self.opening.units)

    def growth_rate(self) -> Fraction | None:
        if self.opening.units == 0:
            return None
        return Fraction(self.net_change().units, self.opening.units)


def mrr(subscriptions: list[Subscription], currency: str) -> Money:
    total = Money.zero(currency)
    for subscription in subscriptions:
        if subscription.amount.currency != currency:
            raise Refused(
                f"subscription for {subscription.customer_id!r} is in "
                f"{subscription.amount.currency}, not {currency}"
            )
        total = total + subscription.monthly_value()
    return total


def arr(subscriptions: list[Subscription], currency: str) -> Money:
    monthly = mrr(subscriptions, currency)
    return Money.from_minor(monthly.units * 12, currency)


def movement(
    opening: list[Subscription], closing: list[Subscription], currency: str
) -> RevenueMovement:
    before = {s.customer_id: s.monthly_value() for s in opening}
    after = {s.customer_id: s.monthly_value() for s in closing}
    zero = Money.zero(currency)
    new = zero
    expansion = zero
    contraction = zero
    churn = zero
    for customer, value in after.items():
        if customer not in before:
            new = new + value
        elif value > before[customer]:
            expansion = expansion + (value - before[customer])
        elif value < before[customer]:
            contraction = contraction + (before[customer] - value)
    for customer, value in before.items():
        if customer not in after:
            churn = churn + value
    return RevenueMovement(
        new=new,
        expansion=expansion,
        contraction=contraction,
        churn=churn,
        opening=mrr(opening, currency),
        closing=mrr(closing, currency),
    )


def lifetime_value(monthly: Money, monthly_churn: Fraction) -> Money:
    if monthly_churn <= 0 or monthly_churn > 1:
        raise Refused(
            "lifetime value needs a churn rate above zero and at most one; a "
            "customer base that never churns has no finite lifetime"
        )
    return round_money(
        Fraction(monthly.units) / monthly_churn, monthly.currency, Rounding.HALF_EVEN
    )
