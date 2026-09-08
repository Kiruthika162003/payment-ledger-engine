"""Segment reporting: which parts of a business are big enough to report separately.

A conglomerate reporting one revenue figure tells an investor
nothing about whether the profitable half is subsidizing the
failing one, so accounting standards require the material parts to
be reported separately. Material is defined by thresholds rather
than judgement, which is what makes this computable: a segment is
reportable if its revenue, or its absolute profit or loss, or its
assets reach a tenth of the combined total. The absolute is the
subtle part, because a segment losing heavily is exactly as
interesting as one earning heavily and comparing signed profits
against a combined total that nets them out would hide the loss.
There is a second rule this module also applies: the reportable
segments together must cover at least three quarters of external
revenue, and if they do not, more segments are added, largest
first, until they do. Everything left over is aggregated into an
all other category rather than dropped, so the segments still sum
to the entity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money

MATERIALITY = Fraction(1, 10)
COVERAGE = Fraction(3, 4)
OTHER = "all other segments"


@dataclass(frozen=True)
class Segment:
    name: str
    revenue: Money
    profit: Money
    assets: Money

    def __post_init__(self) -> None:
        self.profit.same_currency(self.revenue)
        self.assets.same_currency(self.revenue)
        if self.revenue.is_negative() or self.assets.is_negative():
            raise Refused("segment revenue and assets are not negative")


@dataclass
class SegmentReport:
    currency: str
    segments: list[Segment] = field(default_factory=list)

    def add(self, segment: Segment) -> Segment:
        if segment.revenue.currency != self.currency:
            raise Refused(
                f"segment {segment.name!r} reports in {segment.revenue.currency}, "
                f"not {self.currency}"
            )
        if any(existing.name == segment.name for existing in self.segments):
            raise Refused(f"segment {segment.name!r} is already in the report")
        self.segments.append(segment)
        return segment

    def total_revenue(self) -> Money:
        total = Money.zero(self.currency)
        for segment in self.segments:
            total = total + segment.revenue
        return total

    def total_assets(self) -> Money:
        total = Money.zero(self.currency)
        for segment in self.segments:
            total = total + segment.assets
        return total

    def combined_absolute_profit(self) -> Money:
        # Absolute, so a heavy loss counts as much as a heavy profit.
        total = Money.zero(self.currency)
        for segment in self.segments:
            total = total + abs(segment.profit)
        return total

    def meets_threshold(self, segment: Segment) -> bool:
        revenue_total = self.total_revenue().units
        profit_total = self.combined_absolute_profit().units
        asset_total = self.total_assets().units
        checks = [
            revenue_total and Fraction(segment.revenue.units, revenue_total) >= MATERIALITY,
            profit_total
            and Fraction(abs(segment.profit).units, profit_total) >= MATERIALITY,
            asset_total and Fraction(segment.assets.units, asset_total) >= MATERIALITY,
        ]
        return any(bool(check) for check in checks)

    def reportable(self) -> list[Segment]:
        chosen = [s for s in self.segments if self.meets_threshold(s)]
        rest = sorted(
            (s for s in self.segments if s not in chosen),
            key=lambda s: -s.revenue.units,
        )
        # Top up until three quarters of revenue is covered, largest first.
        for segment in rest:
            if self.coverage(chosen) >= COVERAGE:
                break
            chosen.append(segment)
        return sorted(chosen, key=lambda s: s.name)

    def coverage(self, chosen: list[Segment]) -> Fraction:
        total = self.total_revenue().units
        if total == 0:
            return Fraction(1)
        covered = sum(segment.revenue.units for segment in chosen)
        return Fraction(covered, total)

    def meets_coverage(self) -> bool:
        return self.coverage(self.reportable()) >= COVERAGE

    def other_segment(self) -> Segment:
        chosen = {segment.name for segment in self.reportable()}
        revenue = Money.zero(self.currency)
        profit = Money.zero(self.currency)
        assets = Money.zero(self.currency)
        for segment in self.segments:
            if segment.name in chosen:
                continue
            revenue = revenue + segment.revenue
            profit = profit + segment.profit
            assets = assets + segment.assets
        return Segment(OTHER, revenue, profit, assets)

    def presented(self) -> list[Segment]:
        lines = self.reportable()
        other = self.other_segment()
        if other.revenue.is_positive() or other.assets.is_positive():
            lines = [*lines, other]
        return lines

    def sums_to_the_entity(self) -> bool:
        total = Money.zero(self.currency)
        for segment in self.presented():
            total = total + segment.revenue
        return total == self.total_revenue()
