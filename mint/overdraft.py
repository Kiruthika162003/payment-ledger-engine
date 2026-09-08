"""Overdraft fees: charged per item, capped per day, and ordered so the cap means something.

Overdraft fees are where the order of processing becomes a policy
with a price. A bank that posts the day's transactions largest
first drives the balance negative sooner and charges more items an
overdraft fee than one posting smallest first, from identical
transactions on identical balances. That reordering was the subject
of real litigation, so this module makes the ordering explicit and
lets both be computed and compared rather than burying whichever
the code happened to do. Fees are capped per day, because an
uncapped per-item fee turns a small shortfall into a catastrophic
one, and a de minimis threshold suppresses the fee on an overdraft
too small to be worth charging for, which is the rule that keeps a
customer from being charged thirty-five dollars for being two cents
short. An extended overdraft fee applies when the account stays
negative for a run of days, and it is charged once per run rather
than compounding, since a customer already unable to cover the
balance is not helped by charging them faster.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mint.errors import Refused
from mint.money import Money


class PostingOrder(Enum):
    LARGEST_FIRST = "largest_first"
    SMALLEST_FIRST = "smallest_first"
    AS_PRESENTED = "as_presented"


@dataclass(frozen=True)
class OverdraftPolicy:
    item_fee: Money
    daily_cap_items: int
    de_minimis: Money
    extended_fee: Money
    extended_after_days: int

    def __post_init__(self) -> None:
        if self.daily_cap_items < 1:
            raise Refused("a daily cap allows at least one fee")
        if self.item_fee.is_negative() or self.extended_fee.is_negative():
            raise Refused("a fee is not negative")
        if self.de_minimis.is_negative():
            raise Refused("a de minimis threshold is not negative")
        if self.extended_after_days < 1:
            raise Refused("an extended overdraft runs at least a day")


@dataclass(frozen=True)
class DayResult:
    order: PostingOrder
    fees_charged: int
    fee_total: Money
    closing_balance: Money
    items_overdrawn: tuple[int, ...]


def _ordered(amounts: list[Money], order: PostingOrder) -> list[Money]:
    if order is PostingOrder.LARGEST_FIRST:
        return sorted(amounts, key=lambda item: -item.units)
    if order is PostingOrder.SMALLEST_FIRST:
        return sorted(amounts, key=lambda item: item.units)
    return list(amounts)


def process_day(
    opening: Money,
    debits: list[Money],
    policy: OverdraftPolicy,
    order: PostingOrder = PostingOrder.AS_PRESENTED,
) -> DayResult:
    for amount in debits:
        amount.same_currency(opening)
        if not amount.is_positive():
            raise Refused("a debit presented against an account is positive")
    balance = opening
    fees = 0
    overdrawn: list[int] = []
    for index, amount in enumerate(_ordered(debits, order)):
        balance = balance - amount
        if not balance.is_negative():
            continue
        shortfall = -balance
        if shortfall <= policy.de_minimis:
            continue
        if fees >= policy.daily_cap_items:
            continue
        fees += 1
        overdrawn.append(index)
        balance = balance - policy.item_fee
    return DayResult(
        order=order,
        fees_charged=fees,
        fee_total=Money.from_minor(policy.item_fee.units * fees, opening.currency),
        closing_balance=balance,
        items_overdrawn=tuple(overdrawn),
    )


def compare_orders(
    opening: Money, debits: list[Money], policy: OverdraftPolicy
) -> dict[PostingOrder, DayResult]:
    # The comparison that made this a matter for the courts.
    return {order: process_day(opening, debits, policy, order) for order in PostingOrder}


def reordering_cost(
    opening: Money, debits: list[Money], policy: OverdraftPolicy
) -> Money:
    results = compare_orders(opening, debits, policy)
    worst = results[PostingOrder.LARGEST_FIRST].fee_total
    best = results[PostingOrder.SMALLEST_FIRST].fee_total
    return worst - best


def extended_fee_due(days_negative: int, policy: OverdraftPolicy) -> Money:
    # Charged once per run, not compounded: charging faster does not help a
    # customer who already cannot cover the balance.
    if days_negative < policy.extended_after_days:
        return Money.zero(policy.extended_fee.currency)
    return policy.extended_fee
