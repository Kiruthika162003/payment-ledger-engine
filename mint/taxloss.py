"""Tax losses: carried forward, used oldest first, and capped so some tax is always paid.

A company that loses money one year can usually set that loss
against profits in later years, which is fair, since taxing the
good years while ignoring the bad ones would tax a business that
never made money overall. The rules around it are what this module
encodes. Losses expire, so they are used oldest first, because a
loss with two years left is worth more than one with ten and using
the newer first wastes the older. Many jurisdictions cap the
proportion of a year's profit that losses may shelter, so a
profitable company always pays something; this module applies that
cap and reports the tax still due despite having losses available,
which is the figure that surprises people. Expired losses are
reported separately from used ones, because a loss that expired
unused is a real cost and burying it in the utilization number
hides how much the company failed to recover. A loss is never used
twice and never used before it arose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass
class LossYear:
    year: int
    amount: Money
    expires_after: int
    used: Money | None = None

    def __post_init__(self) -> None:
        if not self.amount.is_positive():
            raise Refused("a tax loss carried forward is a positive amount")
        if self.expires_after < self.year:
            raise Refused("a loss cannot expire before the year it arose")
        if self.used is None:
            self.used = Money.zero(self.amount.currency)

    def remaining(self) -> Money:
        return self.amount - self.used

    def is_expired(self, in_year: int) -> bool:
        return in_year > self.expires_after

    def is_available(self, in_year: int) -> bool:
        return (
            in_year >= self.year
            and not self.is_expired(in_year)
            and self.remaining().is_positive()
        )


@dataclass(frozen=True)
class Utilization:
    year: int
    profit: Money
    shelterable: Money
    used: Money
    taxable_after: Money
    losses_expired: Money

    def sheltered_everything(self) -> bool:
        return self.taxable_after.is_zero()

    def tax_due_despite_losses(self) -> bool:
        return self.taxable_after.is_positive()


@dataclass
class LossPool:
    currency: str
    shelter_cap: Fraction = Fraction(1)
    years: list[LossYear] = field(default_factory=list)
    expired_total: Money | None = None

    def __post_init__(self) -> None:
        if self.shelter_cap <= 0 or self.shelter_cap > 1:
            raise Refused(
                "a shelter cap is a fraction above zero and at most one"
            )
        if self.expired_total is None:
            self.expired_total = Money.zero(self.currency)

    def record_loss(self, year: int, amount: Money, expires_after: int) -> LossYear:
        if amount.currency != self.currency:
            raise Refused(
                f"this pool is in {self.currency}, not {amount.currency}"
            )
        if any(existing.year == year for existing in self.years):
            raise Refused(f"a loss for {year} is already in the pool")
        loss = LossYear(year, amount, expires_after)
        self.years.append(loss)
        self.years.sort(key=lambda item: item.year)
        return loss

    def available(self, in_year: int) -> Money:
        total = Money.zero(self.currency)
        for loss in self.years:
            if loss.is_available(in_year):
                total = total + loss.remaining()
        return total

    def expire(self, in_year: int) -> Money:
        lost = Money.zero(self.currency)
        for loss in self.years:
            if loss.is_expired(in_year) and loss.remaining().is_positive():
                lost = lost + loss.remaining()
                loss.used = loss.amount
        self.expired_total = self.expired_total + lost
        return lost

    def apply(self, year: int, profit: Money) -> Utilization:
        if profit.currency != self.currency:
            raise Refused(f"this pool is in {self.currency}, not {profit.currency}")
        if profit.is_negative():
            raise Refused("losses shelter a profit, not another loss")
        expired = self.expire(year)
        shelterable = scale(profit, self.shelter_cap, Rounding.HALF_EVEN)
        remaining_to_shelter = shelterable
        used = Money.zero(self.currency)
        # Oldest first: a loss with less time left is worth more now.
        for loss in sorted(self.years, key=lambda item: item.year):
            if not remaining_to_shelter.is_positive():
                break
            if not loss.is_available(year):
                continue
            take = min(loss.remaining(), remaining_to_shelter)
            loss.used = loss.used + take
            used = used + take
            remaining_to_shelter = remaining_to_shelter - take
        return Utilization(
            year=year,
            profit=profit,
            shelterable=shelterable,
            used=used,
            taxable_after=profit - used,
            losses_expired=expired,
        )

    def total_unused(self) -> Money:
        total = Money.zero(self.currency)
        for loss in self.years:
            total = total + loss.remaining()
        return total
