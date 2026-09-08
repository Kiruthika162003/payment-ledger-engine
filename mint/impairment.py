"""Impairment: writing an asset down to its real worth, and the limit on writing it back.

An asset carried at cost less depreciation may still be worth less
than that, because the factory it sits in lost its contract or the
technology moved on. Impairment is the write-down to the
recoverable amount, which is the higher of what the asset could be
sold for and what it will earn in use, and taking the higher of the
two is the rule that stops a business writing down an asset it is
still profitably using merely because nobody would buy it. This
module computes that comparison and the write-down. The reversal
rule is the part worth encoding carefully: if the asset recovers,
the impairment can be reversed, but never above the carrying value
the asset would have had if it had never been impaired, because
reversing past that point would use an impairment as a way to
manufacture a future gain. So the module tracks what the
depreciated cost would have been and caps any reversal there,
reporting both the reversal taken and the reversal refused.
"""

from __future__ import annotations

from dataclasses import dataclass

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class RecoverableAmount:
    fair_value_less_costs: Money
    value_in_use: Money

    def __post_init__(self) -> None:
        self.value_in_use.same_currency(self.fair_value_less_costs)
        if self.fair_value_less_costs.is_negative() or self.value_in_use.is_negative():
            raise Refused("a recoverable amount is not negative")

    def amount(self) -> Money:
        # The higher of the two: an asset still earning is not impaired just
        # because nobody would buy it.
        if self.fair_value_less_costs > self.value_in_use:
            return self.fair_value_less_costs
        return self.value_in_use

    def driven_by_use(self) -> bool:
        return self.value_in_use >= self.fair_value_less_costs


@dataclass
class ImpairableAsset:
    id: str
    carrying_value: Money
    unimpaired_carrying_value: Money | None = None
    accumulated_impairment: Money | None = None

    def __post_init__(self) -> None:
        if self.carrying_value.is_negative():
            raise Refused("a carrying value is not negative")
        if self.unimpaired_carrying_value is None:
            self.unimpaired_carrying_value = self.carrying_value
        if self.accumulated_impairment is None:
            self.accumulated_impairment = Money.zero(self.carrying_value.currency)

    def is_impaired(self) -> bool:
        return self.accumulated_impairment.is_positive()

    def test(self, recoverable: RecoverableAmount) -> Money:
        recoverable.amount().same_currency(self.carrying_value)
        shortfall = self.carrying_value - recoverable.amount()
        if shortfall.is_positive():
            return shortfall
        return Money.zero(self.carrying_value.currency)

    def impair(self, recoverable: RecoverableAmount) -> Money:
        loss = self.test(recoverable)
        if loss.is_zero():
            raise Refused(
                f"asset {self.id!r} is not impaired; its recoverable amount is "
                "at or above its carrying value"
            )
        self.carrying_value = self.carrying_value - loss
        self.accumulated_impairment = self.accumulated_impairment + loss
        return loss

    def reversal_ceiling(self) -> Money:
        return self.unimpaired_carrying_value

    def reverse(self, recoverable: RecoverableAmount) -> tuple[Money, Money]:
        if not self.is_impaired():
            raise Refused(
                f"asset {self.id!r} carries no impairment to reverse"
            )
        target = recoverable.amount()
        target.same_currency(self.carrying_value)
        if target <= self.carrying_value:
            raise Refused(
                f"asset {self.id!r} has not recovered; its recoverable amount "
                "is at or below what it already carries"
            )
        wanted = target - self.carrying_value
        headroom = self.reversal_ceiling() - self.carrying_value
        taken = wanted if wanted <= headroom else headroom
        refused = wanted - taken
        self.carrying_value = self.carrying_value + taken
        self.accumulated_impairment = self.accumulated_impairment - taken
        # The refused portion is reported rather than dropped: reversing past
        # the never-impaired value would manufacture a gain.
        return taken, refused

    def depreciate(self, amount: Money) -> Money:
        amount.same_currency(self.carrying_value)
        if not amount.is_positive():
            raise Refused("a depreciation charge is positive")
        if amount > self.carrying_value:
            raise Refused("depreciation cannot take a carrying value below zero")
        self.carrying_value = self.carrying_value - amount
        self.unimpaired_carrying_value = self.unimpaired_carrying_value - amount
        return self.carrying_value
