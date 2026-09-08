"""Annuities: what a stream of equal payments is worth, and when they fall matters.

An annuity is a series of equal payments, and its value depends on
a detail that sounds pedantic and is worth real money: whether each
payment falls at the end of its period or the beginning. An
ordinary annuity pays in arrears, like most loans; an annuity due
pays in advance, like rent, and because every payment arrives one
period earlier it is worth exactly one period's growth more, which
is the factor of one plus the rate that separates the two formulas.
A system that uses the arrears formula for a lease paid in advance
understates the liability by that factor on every contract. This
module computes present and future value for both, in exact
fractions so a schedule built from them closes rather than drifting,
and rounds only when handing back money. The zero-rate case is
handled separately rather than by a formula that divides by the
rate, because an interest-free stream is a real arrangement and its
value is simply the payment times the count, which the general
formula cannot express without dividing by zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, round_money


@dataclass(frozen=True)
class AnnuityTerms:
    payment: Money
    rate: Fraction
    periods: int
    due: bool = False

    def __post_init__(self) -> None:
        if self.periods < 1:
            raise Refused("an annuity runs for at least one period")
        if self.rate < 0:
            raise Refused("an annuity rate is not negative")
        if not self.payment.is_positive():
            raise Refused("an annuity pays a positive amount each period")


def present_value_factor(rate: Fraction, periods: int, due: bool = False) -> Fraction:
    if periods < 1:
        raise Refused("a factor covers at least one period")
    if rate == 0:
        base = Fraction(periods)
    else:
        base = (1 - (1 + rate) ** (-periods)) / rate
    return base * (1 + rate) if due else base


def future_value_factor(rate: Fraction, periods: int, due: bool = False) -> Fraction:
    if periods < 1:
        raise Refused("a factor covers at least one period")
    if rate == 0:
        base = Fraction(periods)
    else:
        base = ((1 + rate) ** periods - 1) / rate
    return base * (1 + rate) if due else base


def present_value(
    terms: AnnuityTerms, mode: Rounding = Rounding.HALF_EVEN
) -> Money:
    factor = present_value_factor(terms.rate, terms.periods, terms.due)
    return round_money(terms.payment.times(factor), terms.payment.currency, mode)


def future_value(terms: AnnuityTerms, mode: Rounding = Rounding.HALF_EVEN) -> Money:
    factor = future_value_factor(terms.rate, terms.periods, terms.due)
    return round_money(terms.payment.times(factor), terms.payment.currency, mode)


def payment_for_present_value(
    target: Money, rate: Fraction, periods: int, due: bool = False,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    if not target.is_positive():
        raise Refused("an annuity funds a positive present value")
    factor = present_value_factor(rate, periods, due)
    return round_money(Fraction(target.units) / factor, target.currency, mode)


def payment_for_future_value(
    target: Money, rate: Fraction, periods: int, due: bool = False,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    if not target.is_positive():
        raise Refused("an annuity accumulates a positive future value")
    factor = future_value_factor(rate, periods, due)
    return round_money(Fraction(target.units) / factor, target.currency, mode)


def advantage_of_paying_in_advance(terms: AnnuityTerms) -> Money:
    # Exactly one period's growth: the whole difference between the two forms.
    arrears = present_value(AnnuityTerms(terms.payment, terms.rate, terms.periods, False))
    advance = present_value(AnnuityTerms(terms.payment, terms.rate, terms.periods, True))
    return advance - arrears
