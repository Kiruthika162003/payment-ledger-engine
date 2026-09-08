"""Loyalty points: earned on spend, redeemed for money, counted as whole points.

A points program is a small second currency the merchant issues,
and treating it casually is how programs leak margin. Points are
whole things, not fractions, so earning floors rather than rounds:
a program that gives one point per dollar gives three points for
three dollars and ninety-nine cents, not three and a bit rounded to
four, because rounding earning up hands out points nobody paid for.
Redemption runs the other way, converting points back to money at
the program's stated rate, and it refuses to redeem more points
than the member holds, since a negative balance is the merchant
funding a discount out of points that were never earned. The value
of a redemption is money, computed from the points and the rate and
rounded once, so the discount a member sees reconciles against the
points it cost. The balance is the earned points less the redeemed,
kept as an integer, and the module reports it plainly, because the
one question a member always asks, how many points do I have,
deserves an exact answer rather than an estimate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass
class LoyaltyAccount:
    member_id: str
    currency: str
    earn_rate: Fraction
    redeem_value: Fraction
    earned: int = 0
    redeemed: int = 0
    history: list[tuple[str, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.earn_rate < 0 or self.redeem_value <= 0:
            raise Refused("earn and redemption rates are positive")

    def balance(self) -> int:
        return self.earned - self.redeemed

    def earn_on(self, spend: Money) -> int:
        if spend.currency != self.currency:
            raise Refused(
                f"this program earns on {self.currency}, not {spend.currency}"
            )
        if not spend.is_positive():
            raise Refused("points are earned on positive spend")
        points = math.floor(Fraction(spend.units) * self.earn_rate / 100)
        self.earned += points
        self.history.append(("earn", points))
        return points

    def redeem(self, points: int) -> Money:
        if points <= 0:
            raise Refused("a redemption spends a positive number of points")
        if points > self.balance():
            raise Refused(
                f"a redemption of {points} points exceeds the {self.balance()} "
                f"held by member {self.member_id!r}"
            )
        self.redeemed += points
        self.history.append(("redeem", points))
        return round_money(
            Fraction(points) * self.redeem_value, self.currency, Rounding.HALF_EVEN
        )
