"""Assay: exact conversion is lossless and rounded conversion stays within a cent.

Currency conversion is where a ledger most easily leaks money, so
two claims are worth measuring. The first is that the exact,
unrounded conversion is perfectly reversible: convert a sum to
another currency and back at the reciprocal rate and the exact
fraction lands on the original to the unit, which it must, since
multiplying by a ratio and then its inverse is the identity. The
second is the practical one: the rounded conversion that a real
posting uses cannot round-trip perfectly, because rounding throws
away the fractional cent, but the drift must never exceed a single
minor unit, and this assay measures the worst drift across a
spread of amounts and awkward rates rather than trusting the one
in the docstring. The exponent-carrying case is measured too,
since converting dollars to yen without accounting for the yen
having no minor unit is the mistake that misstates a figure by a
factor of a hundred.
"""

from __future__ import annotations

from fractions import Fraction

from mint.assays.framework import Finding, assay
from mint.conversion import convert_at, exact_minor
from mint.money import Money

_RATES = [Fraction(7, 13), Fraction(9, 10), Fraction(150), Fraction(1, 3), Fraction(123, 100)]


@assay("fx", "is conversion lossless exactly and within a cent when rounded")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    start = Money.of("100.00", "USD")
    there = exact_minor(start, "EUR", Fraction(7, 13))
    back = there * Fraction(13, 7)
    findings.append(Finding("exact round trip drift", back - Fraction(start.units), 0))

    yen = convert_at(Money.of("10.00", "USD"), "JPY", Fraction(150))
    findings.append(Finding("ten dollars to yen at 150", yen.units, 1500))

    worst = 0
    for rate in _RATES:
        for major in (1, 7, 100, 4999):
            original = Money.of(str(major), "USD")
            forward = convert_at(original, "EUR", rate)
            returned = convert_at(forward, "USD", 1 / rate)
            worst = max(worst, abs(returned.units - original.units))
    findings.append(Finding("worst rounded round-trip drift within one cent", worst <= 1, True))
    findings.append(Finding("worst rounded round-trip drift measured", worst, 1))

    return findings
