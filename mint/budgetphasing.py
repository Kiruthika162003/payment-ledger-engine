"""Phasing a budget: spreading an annual number across months that are not alike.

An annual budget is agreed as one number and then has to be spread
across the year so that each month can be compared against it, and
the spread is where the comparison becomes useful or useless.
Spreading evenly is right for rent and wrong for almost everything
else: a retailer that budgets a twelfth of its revenue to January
will report a catastrophic variance every January and a triumphant
one every December, and after two years nobody reads the report.
So this module offers the profiles that actually match how money
moves: even, weighted by a supplied seasonal shape, weighted by
working days, and front or back loaded. Whatever the profile, the
phased amounts must sum to the annual figure exactly, which is
enforced through the cent-conserving allocation rather than hoped
for, because a phasing that does not add back to the budget means
every year-to-date comparison is wrong by a growing amount.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.calendarutil import add_months, days_in_month
from mint.errors import Refused
from mint.money import Money
from mint.rounding import allocate


class Profile(Enum):
    EVEN = "even"
    SEASONAL = "seasonal"
    WORKING_DAYS = "working_days"
    FRONT_LOADED = "front_loaded"
    BACK_LOADED = "back_loaded"


@dataclass(frozen=True)
class PhasedBudget:
    annual: Money
    profile: Profile
    months: tuple[tuple[datetime.date, int], ...]

    def amount_for(self, month: datetime.date) -> Money:
        for when, units in self.months:
            if when.year == month.year and when.month == month.month:
                return Money.from_minor(units, self.annual.currency)
        raise Refused(f"{month.isoformat()} is outside this budget year")

    def sums_to_annual(self) -> bool:
        return sum(units for _, units in self.months) == self.annual.units

    def year_to_date(self, through: datetime.date) -> Money:
        units = sum(
            value
            for when, value in self.months
            if (when.year, when.month) <= (through.year, through.month)
        )
        return Money.from_minor(units, self.annual.currency)

    def peak_month(self) -> datetime.date:
        return max(self.months, key=lambda row: row[1])[0]


def _working_day_weights(start: datetime.date, count: int) -> list[Fraction]:
    weights: list[Fraction] = []
    for offset in range(count):
        month = add_months(start, offset)
        days = days_in_month(month.year, month.month)
        working = sum(
            1
            for day in range(1, days + 1)
            if datetime.date(month.year, month.month, day).weekday() < 5
        )
        weights.append(Fraction(working))
    return weights


def _profile_weights(
    profile: Profile,
    start: datetime.date,
    count: int,
    seasonal: list[Fraction] | None,
) -> list[Fraction]:
    if profile is Profile.EVEN:
        return [Fraction(1)] * count
    if profile is Profile.WORKING_DAYS:
        return _working_day_weights(start, count)
    if profile is Profile.FRONT_LOADED:
        return [Fraction(count - index) for index in range(count)]
    if profile is Profile.BACK_LOADED:
        return [Fraction(index + 1) for index in range(count)]
    if seasonal is None:
        raise Refused(
            "a seasonal phasing needs a shape; without one it is just an even "
            "spread wearing a different name"
        )
    if len(seasonal) != count:
        raise Refused(
            f"the seasonal shape has {len(seasonal)} weights for {count} months"
        )
    if any(weight < 0 for weight in seasonal):
        raise Refused("a seasonal weight is not negative")
    return list(seasonal)


def phase(
    annual: Money,
    start: datetime.date,
    profile: Profile = Profile.EVEN,
    months: int = 12,
    seasonal: list[Fraction] | None = None,
) -> PhasedBudget:
    if months < 1:
        raise Refused("a budget year covers at least one month")
    if not annual.is_positive():
        raise Refused("a phased budget starts from a positive annual figure")
    weights = _profile_weights(profile, start, months, seasonal)
    # Allocated rather than divided, so the phasing adds back to the budget.
    shares = allocate(annual, weights)
    rows = tuple(
        (add_months(start, offset), share.units)
        for offset, share in enumerate(shares)
    )
    return PhasedBudget(annual=annual, profile=profile, months=rows)


def variance_to_date(
    budget: PhasedBudget, actual: Money, through: datetime.date
) -> Money:
    return actual - budget.year_to_date(through)
