"""Conversion: turning money in one currency into another, exponents and all.

Converting money is not simply multiplying by a rate, because the
two currencies may not divide their major unit the same way. A
rate quotes major units against major units, one dollar buys so
many yen, but the amounts are stored in minor units, and yen have
no minor unit while dollars have a hundred, so a conversion that
multiplies cents by the rate and calls the result yen is off by a
factor of a hundred. This module carries the exponents through the
arithmetic explicitly: it converts the source minor units to the
target's minor units by the rate and by the ratio of the two
currencies' minor-per-major factors, keeping the whole calculation
exact as a fraction and rounding only at the end with the mode the
caller names. The exact fraction is available alongside the
rounded money, because revaluation and reconciliation sometimes
need the unrounded figure to avoid compounding a half-cent across
a thousand lines. A conversion whose rate the table cannot supply
raises rather than guessing, so a missing rate stops the posting
instead of silently valuing a position at zero.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint import currency as currency_module
from mint.fxrate import RateTable
from mint.money import Money
from mint.rounding import Rounding, round_money


def exact_minor(money: Money, to_currency: str, rate: Fraction) -> Fraction:
    source = currency_module.get(money.currency)
    target = currency_module.get(to_currency)
    return (
        Fraction(money.units)
        * rate
        * Fraction(target.minor_per_major(), source.minor_per_major())
    )


def convert_at(
    money: Money,
    to_currency: str,
    rate: Fraction,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    to_currency = to_currency.upper()
    if money.currency == to_currency:
        return money
    return round_money(exact_minor(money, to_currency, rate), to_currency, mode)


def convert(
    money: Money,
    to_currency: str,
    rates: RateTable,
    date: datetime.date,
    mode: Rounding = Rounding.HALF_EVEN,
) -> Money:
    to_currency = to_currency.upper()
    if money.currency == to_currency:
        return money
    rate = rates.rate_on(money.currency, to_currency, date)
    return convert_at(money, to_currency, rate, mode)


def convert_exact(
    money: Money,
    to_currency: str,
    rates: RateTable,
    date: datetime.date,
) -> Fraction:
    to_currency = to_currency.upper()
    if money.currency == to_currency:
        return Fraction(money.units)
    rate = rates.rate_on(money.currency, to_currency, date)
    return exact_minor(money, to_currency, rate)
