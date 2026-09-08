"""Volume rebates: money owed back once a customer buys enough, accrued as they go.

A volume rebate promises a customer money back if their purchases
over a year reach a threshold, and the accounting question is when
to recognize it. Waiting until the threshold is crossed overstates
profit for eleven months and then takes a large hit; recognizing
the full rebate from the first order understates it if the customer
never gets there. The defensible answer is to accrue the rebate a
business expects to owe, based on where purchases actually stand,
and adjust as the picture changes. This module tracks purchases
against a tiered rebate schedule, reports the rebate earned at the
current volume, and reports the incremental accrual needed to move
from what has already been accrued to what is now owed, which is
the figure that goes to the ledger each period. Tiers are volume
style: reaching a threshold applies its rate to all purchases, not
just those above the line, which is how these contracts are almost
always written and which makes the accrual jump at each threshold
rather than climbing smoothly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class RebateTier:
    threshold: Money
    rate: Fraction

    def __post_init__(self) -> None:
        if self.rate < 0 or self.rate >= 1:
            raise Refused("a rebate rate is a fraction below one")
        if self.threshold.is_negative():
            raise Refused("a rebate threshold is not negative")


@dataclass
class RebateAgreement:
    customer_id: str
    currency: str
    tiers: tuple[RebateTier, ...]
    purchases: Money | None = None
    accrued: Money | None = None
    history: list[Money] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.tiers:
            raise Refused("a rebate agreement needs at least one tier")
        thresholds = [tier.threshold.units for tier in self.tiers]
        if thresholds != sorted(thresholds) or len(set(thresholds)) != len(thresholds):
            raise Refused("rebate tiers must have strictly increasing thresholds")
        for tier in self.tiers:
            if tier.threshold.currency != self.currency:
                raise Refused(
                    f"tier threshold is in {tier.threshold.currency}, not "
                    f"{self.currency}"
                )
        if self.purchases is None:
            self.purchases = Money.zero(self.currency)
        if self.accrued is None:
            self.accrued = Money.zero(self.currency)

    def buy(self, amount: Money) -> Money:
        if amount.currency != self.currency:
            raise Refused(
                f"this agreement is in {self.currency}, not {amount.currency}"
            )
        if not amount.is_positive():
            raise Refused("a purchase against a rebate is positive")
        self.purchases = self.purchases + amount
        self.history.append(amount)
        return self.purchases

    def current_rate(self) -> Fraction:
        rate = Fraction(0)
        for tier in self.tiers:
            if self.purchases >= tier.threshold:
                rate = tier.rate
        return rate

    def earned(self) -> Money:
        # Volume style: the reached rate applies to everything bought.
        return scale(self.purchases, self.current_rate(), Rounding.HALF_EVEN)

    def accrual_needed(self) -> Money:
        return self.earned() - self.accrued

    def post_accrual(self) -> Money:
        movement = self.accrual_needed()
        self.accrued = self.earned()
        return movement

    def next_threshold(self) -> Money | None:
        for tier in self.tiers:
            if self.purchases < tier.threshold:
                return tier.threshold
        return None

    def to_next_threshold(self) -> Money | None:
        target = self.next_threshold()
        if target is None:
            return None
        return target - self.purchases
