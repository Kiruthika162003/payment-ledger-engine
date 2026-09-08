"""Forecasting: three honest methods, each stating what it assumes.

A forecast is an assumption wearing a number, so the useful thing a
forecasting module can do is name the assumption rather than hide
it. Run rate assumes the most recent period repeats, which is right
for a stable business and wildly wrong the month after a one-off
sale. A linear trend assumes the change per period continues, which
extrapolates growth confidently past the point where anything
grows linearly. A seasonal forecast assumes this year's pattern
repeats last year's shape, which needs at least two cycles of
history to compute at all and is refused outright with less,
because a seasonal index built from one cycle is just that cycle
copied. This module implements all three, refuses each when its
data cannot support it, and reports the method used alongside the
number so a plan built on it can say where the figure came from.
Fitting is done in exact fractions so the same history always
produces the same forecast, which matters more than it sounds:
a forecast that shifts by a cent between runs invites arguments
about whether the business changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


class Method(Enum):
    RUN_RATE = "run_rate"
    LINEAR_TREND = "linear_trend"
    SEASONAL = "seasonal"


@dataclass(frozen=True)
class Forecast:
    method: Method
    values: tuple[int, ...]
    currency: str
    assumption: str

    def as_money(self) -> list[Money]:
        return [Money.from_minor(value, self.currency) for value in self.values]

    def total(self) -> Money:
        return Money.from_minor(sum(self.values), self.currency)

    def first(self) -> Money:
        return Money.from_minor(self.values[0], self.currency)


def _guard(history: list[Money], periods: int, needed: int) -> str:
    if periods < 1:
        raise Refused("a forecast covers at least one future period")
    if len(history) < needed:
        raise Refused(
            f"this method needs at least {needed} periods of history and was "
            f"given {len(history)}"
        )
    currency = history[0].currency
    for value in history:
        if value.currency != currency:
            raise Refused("a history in mixed currencies cannot be forecast")
    return currency


def run_rate(history: list[Money], periods: int) -> Forecast:
    currency = _guard(history, periods, 1)
    last = history[-1].units
    return Forecast(
        method=Method.RUN_RATE,
        values=tuple([last] * periods),
        currency=currency,
        assumption="the most recent period repeats unchanged",
    )


def linear_trend(history: list[Money], periods: int) -> Forecast:
    currency = _guard(history, periods, 2)
    count = len(history)
    xs = [Fraction(index) for index in range(count)]
    ys = [Fraction(value.units) for value in history]
    mean_x = sum(xs, Fraction(0)) / count
    mean_y = sum(ys, Fraction(0)) / count
    products = (
        (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)
    )
    numerator = sum(products, Fraction(0))
    denominator = sum(((x - mean_x) ** 2 for x in xs), Fraction(0))
    if denominator == 0:
        raise Refused("a trend cannot be fitted to a single distinct period")
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    values = []
    for step in range(1, periods + 1):
        point = intercept + slope * Fraction(count - 1 + step)
        values.append(round_money(point, currency, Rounding.HALF_EVEN).units)
    return Forecast(
        method=Method.LINEAR_TREND,
        values=tuple(values),
        currency=currency,
        assumption="the change per period continues at the fitted rate",
    )


def seasonal_indices(history: list[Money], cycle: int) -> list[Fraction]:
    if cycle < 2:
        raise Refused("a seasonal cycle spans at least two periods")
    if len(history) < cycle * 2:
        raise Refused(
            f"a seasonal index needs at least two full cycles of {cycle} "
            "periods; one cycle is just that cycle copied"
        )
    total = sum(value.units for value in history)
    if total == 0:
        raise Refused("a history that sums to zero has no seasonal shape")
    overall_mean = Fraction(total, len(history))
    indices: list[Fraction] = []
    for position in range(cycle):
        slots = [
            Fraction(history[index].units)
            for index in range(position, len(history), cycle)
        ]
        mean = sum(slots, Fraction(0)) / len(slots)
        indices.append(mean / overall_mean)
    return indices


def seasonal(history: list[Money], periods: int, cycle: int) -> Forecast:
    currency = _guard(history, periods, cycle * 2)
    indices = seasonal_indices(history, cycle)
    baseline = Fraction(sum(value.units for value in history), len(history))
    values = []
    for step in range(periods):
        position = (len(history) + step) % cycle
        values.append(
            round_money(baseline * indices[position], currency, Rounding.HALF_EVEN).units
        )
    return Forecast(
        method=Method.SEASONAL,
        values=tuple(values),
        currency=currency,
        assumption="the shape of past cycles repeats around the average level",
    )
