"""Benford's law: leading digits as a smoke alarm, never as a verdict.

In many naturally occurring collections of numbers the leading
digit is not uniform: about thirty percent of values begin with a
one and under five percent with a nine, a consequence of the values
spanning several orders of magnitude. Invented numbers rarely
follow that curve, because people making up amounts spread the
leading digits far more evenly, which is why auditors run this test
across a ledger's amounts. This module computes the observed
distribution of leading digits and the deviation from the expected
one, and it is deliberate about what it claims: a large deviation
is a reason to look, not evidence of anything, and the module names
that in its verdict rather than returning a boolean that invites a
caller to treat suspicion as proof. It also refuses samples too
small to say anything, because a hundred numbers is not enough for
this test to distinguish a fraud from a Tuesday, and reporting a
deviation on twenty amounts would produce exactly the false
confidence the technique is notorious for. Amounts are taken by
absolute value, since a refund is as fabricable as a charge, and
zeros are excluded because zero has no leading digit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money

MINIMUM_SAMPLE = 100


def expected_share(digit: int) -> float:
    if digit < 1 or digit > 9:
        raise Refused("a leading digit runs from one to nine")
    return math.log10(1 + 1 / digit)


def leading_digit(units: int) -> int | None:
    magnitude = abs(units)
    if magnitude == 0:
        return None
    return int(str(magnitude)[0])


@dataclass(frozen=True)
class BenfordReport:
    counts: tuple[int, ...]
    sample_size: int

    def observed_share(self, digit: int) -> Fraction:
        if self.sample_size == 0:
            raise Refused("an empty sample has no distribution")
        return Fraction(self.counts[digit - 1], self.sample_size)

    def deviation(self, digit: int) -> float:
        return float(self.observed_share(digit)) - expected_share(digit)

    def largest_deviation(self) -> tuple[int, float]:
        worst = max(range(1, 10), key=lambda d: abs(self.deviation(d)))
        return worst, self.deviation(worst)

    def mean_absolute_deviation(self) -> float:
        return sum(abs(self.deviation(d)) for d in range(1, 10)) / 9

    def verdict(self) -> str:
        # Thresholds follow the conventional audit bands; they mark where a
        # reviewer should look, and they never claim a finding on their own.
        mad = self.mean_absolute_deviation()
        if mad < 0.006:
            return "close conformity; nothing here suggests looking further"
        if mad < 0.012:
            return "acceptable conformity"
        if mad < 0.015:
            return "marginal conformity; worth a second look"
        return "nonconformity; a reason to look, not evidence of anything"


def analyze(amounts: list[Money], minimum: int = MINIMUM_SAMPLE) -> BenfordReport:
    digits = [leading_digit(amount.units) for amount in amounts]
    usable = [digit for digit in digits if digit is not None]
    if len(usable) < minimum:
        raise Refused(
            f"{len(usable)} usable amounts is too small a sample for a digit "
            f"test; this needs at least {minimum} or it manufactures false "
            "confidence"
        )
    counts = [0] * 9
    for digit in usable:
        counts[digit - 1] += 1
    return BenfordReport(counts=tuple(counts), sample_size=len(usable))
