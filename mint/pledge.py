"""Pledges: a promise to give, recognized now, discounted if it arrives over years.

A donor who promises a hundred thousand over five years has created
an asset the moment the promise is unconditional, and a charity
that waits until the cash arrives understates both its income and
what it is owed. Two adjustments make the figure honest. A promise
payable over years is worth less than its face, so it is discounted
to present value and the discount unwinds as income over the
period. And not every pledge is kept, so an allowance is held for
the share historically not collected, based on what has actually
happened rather than on optimism. A conditional pledge is different
in kind: if the donor has attached a condition the charity has not
yet met, there is no asset at all until it does, and recognizing it
early books income that may never arrive. This module keeps the
conditional and unconditional apart and refuses to recognize the
former.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money, scale


@dataclass
class Pledge:
    id: str
    donor: str
    amount: Money
    promised_on: datetime.date
    years_to_collect: int = 1
    conditional: bool = True
    condition_met: bool = False
    discount_rate: Fraction = Fraction(0)
    received: Money | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a pledge promises a positive amount")
        if self.years_to_collect < 1:
            raise Refused("a pledge is collected over at least one year")
        if self.discount_rate < 0:
            raise Refused("a discount rate is not negative")
        if self.received is None:
            self.received = Money.zero(self.amount.currency)

    def is_recognizable(self) -> bool:
        # A condition the charity has not met means there is no asset yet.
        return not self.conditional or self.condition_met

    def meet_condition(self) -> bool:
        if not self.conditional:
            raise Refused(f"pledge {self.id!r} carries no condition")
        self.condition_met = True
        return True

    def present_value(self) -> Money:
        if not self.is_recognizable():
            return Money.zero(self.amount.currency)
        if self.discount_rate == 0 or self.years_to_collect == 1:
            return self.amount
        factor = (1 + self.discount_rate) ** self.years_to_collect
        return round_money(
            Fraction(self.amount.units) / factor,
            self.amount.currency,
            Rounding.HALF_EVEN,
        )

    def discount(self) -> Money:
        if not self.is_recognizable():
            return Money.zero(self.amount.currency)
        return self.amount - self.present_value()

    def collect(self, amount: Money) -> Money:
        amount.same_currency(self.amount)
        if not self.is_recognizable():
            raise Refused(
                f"pledge {self.id!r} is conditional and its condition has not "
                "been met; there is nothing to collect against yet"
            )
        if not amount.is_positive():
            raise Refused("a collection is a positive amount")
        if self.received + amount > self.amount:
            raise Refused(
                f"collecting {amount.format()} would exceed the "
                f"{self.amount.format()} pledged"
            )
        self.received = self.received + amount
        return self.outstanding()

    def outstanding(self) -> Money:
        return self.amount - self.received

    def is_settled(self) -> bool:
        return self.outstanding().is_zero()


@dataclass
class PledgeRegister:
    currency: str
    uncollectible_rate: Fraction = Fraction(0)
    pledges: list[Pledge] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.uncollectible_rate < 0 or self.uncollectible_rate >= 1:
            raise Refused("an uncollectible rate is a fraction below one")

    def add(self, pledge: Pledge) -> Pledge:
        if pledge.amount.currency != self.currency:
            raise Refused(
                f"pledge {pledge.id!r} is in {pledge.amount.currency}, not "
                f"{self.currency}"
            )
        if any(existing.id == pledge.id for existing in self.pledges):
            raise Refused(f"pledge {pledge.id!r} is already registered")
        self.pledges.append(pledge)
        return pledge

    def recognizable(self) -> list[Pledge]:
        return [pledge for pledge in self.pledges if pledge.is_recognizable()]

    def gross_receivable(self) -> Money:
        total = Money.zero(self.currency)
        for pledge in self.recognizable():
            total = total + pledge.outstanding()
        return total

    def discounted_receivable(self) -> Money:
        total = Money.zero(self.currency)
        for pledge in self.recognizable():
            if pledge.is_settled():
                continue
            total = total + pledge.present_value() - pledge.received
        return total

    def allowance(self) -> Money:
        # From what has actually happened, not from optimism.
        return scale(
            self.discounted_receivable(), self.uncollectible_rate, Rounding.HALF_EVEN
        )

    def carrying_value(self) -> Money:
        return self.discounted_receivable() - self.allowance()

    def unrecognized_total(self) -> Money:
        total = Money.zero(self.currency)
        for pledge in self.pledges:
            if not pledge.is_recognizable():
                total = total + pledge.amount
        return total
