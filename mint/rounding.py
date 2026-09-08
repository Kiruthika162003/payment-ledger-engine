"""Rounding and allocation: splitting a sum so the parts add back to it.

Rounding is where money is created and destroyed, so a ledger
treats it as a decision rather than a default. This module offers
the rounding modes a payments system actually needs, banker's
rounding to even for statistical neutrality, half-up for the
consumer-facing amounts a regulator expects, and the directed
modes for the places where the direction is a policy, and it never
rounds implicitly: a multiplication that lands between two minor
units returns an exact fraction and the caller names the mode that
collapses it. The harder and more important job here is
allocation. Splitting one dollar three ways cannot give three
equal parts, and the naive fix, rounding each third and hoping,
either loses a cent or invents one, so this module uses the
largest-remainder method: floor every share, then hand the
leftover units one at a time to the shares whose exact value was
closest to rounding up. The result always sums back to the
original to the cent, which is the whole point, because a split
that does not reconcile is a split that has quietly moved money.
The first draft of the allocator distributed the leftover to the
first shares in order, which passed the sum test but gave the
earliest party a systematic advantage over thousands of splits;
the largest-remainder version passes the same sum test and also
gives the cent to whoever was owed it, and both facts are proven
by the assays rather than asserted here.
"""

from __future__ import annotations

import math
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


class Rounding(Enum):
    FLOOR = "floor"
    CEILING = "ceiling"
    DOWN = "down"
    UP = "up"
    HALF_UP = "half_up"
    HALF_DOWN = "half_down"
    HALF_EVEN = "half_even"


def round_fraction(value: Fraction, mode: Rounding = Rounding.HALF_EVEN) -> int:
    if mode is Rounding.FLOOR:
        return math.floor(value)
    if mode is Rounding.CEILING:
        return math.ceil(value)
    if mode is Rounding.DOWN:
        return math.trunc(value)
    if mode is Rounding.UP:
        return math.ceil(value) if value > 0 else math.floor(value)
    sign = 1 if value >= 0 else -1
    magnitude = abs(value)
    floor_part = math.floor(magnitude)
    remainder = magnitude - floor_part
    half = Fraction(1, 2)
    if remainder < half:
        rounded = floor_part
    elif remainder > half or mode is Rounding.HALF_UP:
        rounded = floor_part + 1
    elif mode is Rounding.HALF_DOWN:
        rounded = floor_part
    else:
        rounded = floor_part + 1 if floor_part % 2 else floor_part
    return sign * rounded


def round_money(
    minor_units: Fraction, currency: str, mode: Rounding = Rounding.HALF_EVEN
) -> Money:
    return Money.from_minor(round_fraction(minor_units, mode), currency)


def scale(money: Money, factor: int | Fraction, mode: Rounding = Rounding.HALF_EVEN) -> Money:
    return round_money(money.times(factor), money.currency, mode)


def allocate(total: Money, weights: list[int | Fraction]) -> list[Money]:
    if not weights:
        raise Refused("an allocation needs at least one share to split into")
    fractions = [Fraction(w) for w in weights]
    if any(w < 0 for w in fractions):
        raise Refused("a share of an allocation cannot be negative")
    total_weight = sum(fractions, Fraction(0))
    if total_weight == 0:
        raise Refused(
            "the shares of an allocation sum to zero; there is no way to "
            "divide a sum among parts that all claim nothing"
        )
    sign = -1 if total.units < 0 else 1
    pool = abs(total.units)
    exact = [Fraction(pool) * w / total_weight for w in fractions]
    base = [math.floor(value) for value in exact]
    leftover = pool - sum(base)
    order = sorted(
        range(len(fractions)),
        key=lambda i: (exact[i] - base[i], -i),
        reverse=True,
    )
    for position in range(leftover):
        base[order[position]] += 1
    return [Money.from_minor(sign * amount, total.currency) for amount in base]


def split(total: Money, parts: int) -> list[Money]:
    if parts < 1:
        raise Refused("a split needs at least one part")
    return allocate(total, [1] * parts)
