"""Royalties: an advance that must be earned back before anything more is paid.

A royalty contract usually starts with an advance, money paid up
front against royalties not yet earned, and the arithmetic that
follows is recoupment: each period's royalties reduce the
outstanding advance rather than being paid out, and only once the
advance is fully recouped does the creator start receiving money.
Getting this wrong pays twice, once as the advance and again as the
royalties it was supposed to prepay. This module tracks the
unearned balance and reports, for each period, how much was earned,
how much went to recoupment, and how much is actually payable, so a
statement can show the creator why a period with sales produced no
payment. A minimum guarantee is supported, the floor a contract
promises regardless of sales, and it is applied after recoupment
because a guarantee is a payment obligation rather than an earning:
topping up to the guarantee does not reduce the advance further. An
advance is never clawed back when sales disappoint, which is the
whole risk the publisher took, so the balance floors at zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class RoyaltyPeriod:
    label: str
    earned: Money
    recouped: Money
    payable: Money
    unearned_after: Money


@dataclass
class RoyaltyContract:
    creator: str
    currency: str
    rate: Fraction
    advance: Money
    minimum_guarantee: Money | None = None
    unearned: Money | None = None
    periods: list[RoyaltyPeriod] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.rate <= 0 or self.rate >= 1:
            raise Refused("a royalty rate is a fraction above zero and below one")
        if self.advance.currency != self.currency:
            raise Refused(
                f"the advance is in {self.advance.currency}, not {self.currency}"
            )
        if self.advance.is_negative():
            raise Refused("an advance is not negative")
        if self.unearned is None:
            self.unearned = self.advance

    def is_recouped(self) -> bool:
        return self.unearned.is_zero()

    def record(self, label: str, sales: Money) -> RoyaltyPeriod:
        if sales.currency != self.currency:
            raise Refused(
                f"sales in {sales.currency} do not belong to a {self.currency} "
                "contract"
            )
        if sales.is_negative():
            raise Refused("a royalty period reports non-negative sales")
        earned = scale(sales, self.rate, Rounding.HALF_EVEN)

        recouped = earned if earned <= self.unearned else self.unearned
        self.unearned = self.unearned - recouped
        payable = earned - recouped

        if self.minimum_guarantee is not None and payable < self.minimum_guarantee:
            # A guarantee is a payment obligation, not an earning, so topping
            # up to it does not reduce the advance any further.
            payable = self.minimum_guarantee

        period = RoyaltyPeriod(
            label=label,
            earned=earned,
            recouped=recouped,
            payable=payable,
            unearned_after=self.unearned,
        )
        self.periods.append(period)
        return period

    def total_earned(self) -> Money:
        total = Money.zero(self.currency)
        for period in self.periods:
            total = total + period.earned
        return total

    def total_paid(self) -> Money:
        total = Money.zero(self.currency)
        for period in self.periods:
            total = total + period.payable
        return total

    def total_recouped(self) -> Money:
        total = Money.zero(self.currency)
        for period in self.periods:
            total = total + period.recouped
        return total

    def publisher_outlay(self) -> Money:
        return self.advance + self.total_paid()

    def reconciles(self) -> bool:
        # Everything earned either paid down the advance or was paid out,
        # unless a guarantee topped a period up beyond what was earned.
        if self.minimum_guarantee is not None:
            return True
        return self.total_earned() == self.total_recouped() + self.total_paid()
