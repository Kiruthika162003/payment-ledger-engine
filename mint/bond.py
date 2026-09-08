"""Bonds: price as the present value of promises, and the interest earned between coupons.

A bond's price is not a quoted opinion, it is the present value of
what it promises: a stream of coupons plus the principal at
maturity, each discounted at the yield the market demands. That
definition produces the relationship every bond desk lives by,
which this module makes checkable rather than asserting: when the
yield equals the coupon rate the bond prices at par, when the yield
is higher it prices at a discount, and when lower at a premium. The
other thing a ledger needs from a bond is accrued interest. A buyer
between coupon dates owes the seller the interest earned so far,
because the buyer will receive the whole next coupon including the
part the seller held the bond for, and settling without it hands
the buyer money that is not theirs. Accrual is computed on the
day-count convention the bond states rather than a fixed
assumption, since the same bond accrues differently under thirty
over three-sixty than under actual over actual and both conventions
are in daily use.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from fractions import Fraction

from mint.daycount import DayCount, year_fraction
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, scale


@dataclass(frozen=True)
class Bond:
    face: Money
    coupon_rate: Fraction
    periods: int
    coupons_per_year: int = 2
    convention: DayCount = DayCount.THIRTY_360

    def __post_init__(self) -> None:
        if not self.face.is_positive():
            raise Refused("a bond has a positive face value")
        if self.coupon_rate < 0:
            raise Refused("a coupon rate is not negative")
        if self.periods < 1:
            raise Refused("a bond runs for at least one coupon period")
        if self.coupons_per_year < 1:
            raise Refused("a bond pays at least one coupon a year")

    def coupon_payment(self, mode: Rounding = Rounding.HALF_EVEN) -> Money:
        periodic = self.coupon_rate / self.coupons_per_year
        return scale(self.face, periodic, mode)

    def price(self, annual_yield: Fraction, mode: Rounding = Rounding.HALF_EVEN) -> Money:
        if annual_yield < 0:
            raise Refused("a yield used to discount is not negative")
        periodic_yield = annual_yield / self.coupons_per_year
        periodic_coupon = self.coupon_rate / self.coupons_per_year
        coupon_units = Fraction(self.face.units) * periodic_coupon
        if periodic_yield == 0:
            present = coupon_units * self.periods + Fraction(self.face.units)
        else:
            discount = (1 + periodic_yield) ** self.periods
            annuity = (1 - 1 / discount) / periodic_yield
            present = coupon_units * annuity + Fraction(self.face.units) / discount
        return round_money(present, self.face.currency, mode)

    def prices_at_par(self, annual_yield: Fraction) -> bool:
        return self.price(annual_yield) == self.face

    def accrued_interest(
        self,
        last_coupon: datetime.date,
        settlement: datetime.date,
        mode: Rounding = Rounding.HALF_EVEN,
    ) -> Money:
        if settlement < last_coupon:
            raise Refused("settlement cannot precede the last coupon date")
        fraction = year_fraction(last_coupon, settlement, self.convention)
        return round_money(
            self.face.times(self.coupon_rate * fraction), self.face.currency, mode
        )

    def dirty_price(
        self,
        annual_yield: Fraction,
        last_coupon: datetime.date,
        settlement: datetime.date,
    ) -> Money:
        return self.price(annual_yield) + self.accrued_interest(last_coupon, settlement)

    def total_coupons(self) -> Money:
        return Money.from_minor(
            self.coupon_payment().units * self.periods, self.face.currency
        )
