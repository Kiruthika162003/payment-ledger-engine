"""Subscription proration: charging only for the slice of a period actually used.

Subscriptions bill in periods, but customers sign up, upgrade, and
cancel in the middle of them, and proration is the arithmetic that
charges for the slice actually used rather than the whole period.
The rule this module follows is a proportion of days: a plan that
costs a month, joined with some days left in that month, costs that
fraction of the month, computed exactly and rounded once. The
subtlety that trips naive proration is the denominator. The
fraction is days remaining over days in this billing period, not
over a fixed thirty, because a customer who joins with ten days
left in a thirty-one-day month has used ten thirty-firsts and
charging them ten thirtieths overbills them for time they will not
have. An upgrade mid-period is handled as the same proportion
applied to the price difference, so the customer pays the higher
price only for the remaining days and is neither double-charged for
the days already paid at the lower price nor given the upgrade
free. A cancellation credit is the mirror image, the unused slice
returned, and the module computes all three from one honest
day-count so they cannot disagree.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


def _period_fraction(
    effective: datetime.date, period_start: datetime.date, period_end: datetime.date
) -> Fraction:
    if not period_start <= effective <= period_end:
        raise Refused(
            "the effective date falls outside the billing period it prorates"
        )
    total_days = (period_end - period_start).days
    if total_days <= 0:
        raise Refused("a billing period must span at least one day")
    remaining = (period_end - effective).days
    return Fraction(remaining, total_days)


def prorated_charge(
    full_price: Money,
    effective: datetime.date,
    period_start: datetime.date,
    period_end: datetime.date,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    fraction = _period_fraction(effective, period_start, period_end)
    return round_money(full_price.times(fraction), full_price.currency, mode)


def upgrade_charge(
    old_price: Money,
    new_price: Money,
    effective: datetime.date,
    period_start: datetime.date,
    period_end: datetime.date,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    new_price.same_currency(old_price)
    if new_price <= old_price:
        raise Refused("an upgrade raises the price; use a downgrade credit otherwise")
    difference = new_price - old_price
    fraction = _period_fraction(effective, period_start, period_end)
    return round_money(difference.times(fraction), old_price.currency, mode)


def cancellation_credit(
    full_price: Money,
    effective: datetime.date,
    period_start: datetime.date,
    period_end: datetime.date,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    return prorated_charge(full_price, effective, period_start, period_end, mode)
