"""Exchange rates: exact ratios, looked up by date, inverted or triangulated as needed.

An exchange rate is a ratio, and storing it as a floating-point
number reintroduces exactly the drift the money type went to such
lengths to avoid, so rates here are exact fractions: one unit of
the base currency buys this many units of the quote currency, kept
as a numerator over a denominator that never rounds until a
conversion asks it to. Rates carry a date, because a rate is a fact
about a moment and a ledger that converts a March invoice at
September's rate is misstating history; a lookup asks for the rate
in force on a date and gets the most recent quote on or before it,
never a future rate leaking backward. When a direct quote is
missing the table tries the inverse, since knowing that a dollar
buys 0.9 euros is the same knowledge as a euro buying its
reciprocal, and when neither direction is on file it triangulates
through a pivot currency, the way real desks price a thin pair off
two liquid ones. Only when every path fails does it refuse, by
name, with the pair and the date, because a conversion invented
from a rate that does not exist is a number with no provenance, and
provenance is the whole reason to keep a rate table at all.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused, StaleRate


@dataclass(frozen=True)
class Rate:
    base: str
    quote: str
    ratio: Fraction
    as_of: datetime.date

    def inverse(self) -> Rate:
        if self.ratio == 0:
            raise Refused("a zero rate has no inverse")
        return Rate(self.quote, self.base, 1 / self.ratio, self.as_of)


@dataclass
class RateTable:
    pivot: str = "USD"
    quotes: dict[tuple[str, str], list[tuple[datetime.date, Fraction]]] = field(
        default_factory=dict
    )

    def add(self, base: str, quote: str, ratio: Fraction | int, as_of: datetime.date) -> Rate:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            raise Refused("a currency's rate against itself is always one, not a quote")
        value = Fraction(ratio)
        if value <= 0:
            raise Refused("an exchange rate is a positive ratio of one currency to another")
        series = self.quotes.setdefault((base, quote), [])
        series.append((as_of, value))
        series.sort(key=lambda pair: pair[0])
        return Rate(base, quote, value, as_of)

    def _on_or_before(
        self, base: str, quote: str, date: datetime.date
    ) -> Fraction | None:
        series = self.quotes.get((base, quote))
        if not series:
            return None
        chosen: Fraction | None = None
        for as_of, value in series:
            if as_of <= date:
                chosen = value
            else:
                break
        return chosen

    def _direct_or_inverse(
        self, base: str, quote: str, date: datetime.date
    ) -> Fraction | None:
        direct = self._on_or_before(base, quote, date)
        if direct is not None:
            return direct
        inverse = self._on_or_before(quote, base, date)
        if inverse is not None:
            return 1 / inverse
        return None

    def rate_on(self, base: str, quote: str, date: datetime.date) -> Fraction:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return Fraction(1)
        direct = self._direct_or_inverse(base, quote, date)
        if direct is not None:
            return direct
        pivot = self.pivot.upper()
        if pivot not in (base, quote):
            left = self._direct_or_inverse(base, pivot, date)
            right = self._direct_or_inverse(pivot, quote, date)
            if left is not None and right is not None:
                return left * right
        raise StaleRate(
            f"no rate for {base} to {quote} on or before {date.isoformat()}; "
            f"add a direct quote or a path through {pivot}"
        )

    def has_rate(self, base: str, quote: str, date: datetime.date) -> bool:
        try:
            self.rate_on(base, quote, date)
        except StaleRate:
            return False
        return True
