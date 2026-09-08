"""Discounted cash flow: what a stream of future money is worth, and what rate it implies.

Net present value discounts each future cash flow by the time until
it arrives and sums the result, which is the only defensible way to
compare money now against money later. The internal rate of return
inverts the question: it is the discount rate at which the net
present value is exactly zero, the rate the investment implicitly
earns. There is no closed form for it, so this module finds it by
bisection, which is slower than the usual Newton iteration and far
more trustworthy: bisection cannot diverge, and it either brackets
a root or reports honestly that it could not. That honesty matters
because a cash flow stream that changes sign more than once can
have several internal rates of return or none at all, and a solver
that returns the first number it stumbles on presents one of
several answers as though it were the answer. So this module checks
the bracket first and refuses when the sign does not change across
it, naming the problem rather than returning a plausible number
that means nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class CashFlow:
    period: int
    amount: Money

    def __post_init__(self) -> None:
        if self.period < 0:
            raise Refused("a cash flow period is not negative")


def net_present_value(
    flows: list[CashFlow], rate: Fraction, currency: str,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    if rate <= -1:
        raise Refused("a discount rate at or below minus one has no meaning here")
    total = Fraction(0)
    for flow in flows:
        if flow.amount.currency != currency:
            raise Refused(
                f"a cash flow in {flow.amount.currency} cannot be discounted "
                f"into {currency}"
            )
        total += Fraction(flow.amount.units) / (1 + rate) ** flow.period
    return round_money(total, currency, mode)


def _npv_exact(flows: list[CashFlow], rate: Fraction) -> Fraction:
    total = Fraction(0)
    for flow in flows:
        total += Fraction(flow.amount.units) / (1 + rate) ** flow.period
    return total


def sign_changes(flows: list[CashFlow]) -> int:
    signs = [flow.amount.sign() for flow in flows if flow.amount.sign() != 0]
    return sum(1 for a, b in pairwise(signs) if a != b)


def internal_rate_of_return(
    flows: list[CashFlow],
    low: Fraction = Fraction(-9, 10),
    high: Fraction = Fraction(10),
    iterations: int = 200,
) -> Fraction:
    if not flows:
        raise Refused("an internal rate needs cash flows to work from")
    if sign_changes(flows) == 0:
        raise Refused(
            "the cash flows never change sign, so no discount rate brings them "
            "to zero; an all-positive or all-negative stream has no return"
        )
    low_value = _npv_exact(flows, low)
    high_value = _npv_exact(flows, high)
    if (low_value > 0) == (high_value > 0):
        raise Refused(
            "the bracket does not contain a sign change; widen it or accept "
            "that this stream has no single internal rate of return"
        )
    for _ in range(iterations):
        middle = (low + high) / 2
        value = _npv_exact(flows, middle)
        if value == 0:
            return middle
        if (value > 0) == (low_value > 0):
            low = middle
            low_value = value
        else:
            high = middle
    return (low + high) / 2


def payback_period(flows: list[CashFlow]) -> int | None:
    running = 0
    for flow in sorted(flows, key=lambda item: item.period):
        running += flow.amount.units
        if running >= 0 and flow.period > 0:
            return flow.period
    return None


def profitability_index(
    flows: list[CashFlow], rate: Fraction, currency: str
) -> Fraction | None:
    for flow in flows:
        if flow.amount.currency != currency:
            raise Refused(
                f"a cash flow in {flow.amount.currency} cannot be indexed "
                f"against {currency}"
            )
    outflow = sum(
        -flow.amount.units for flow in flows if flow.amount.is_negative()
    )
    if outflow == 0:
        return None
    inflows = [flow for flow in flows if not flow.amount.is_negative()]
    present = _npv_exact(inflows, rate)
    return Fraction(present) / outflow
