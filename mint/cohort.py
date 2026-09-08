"""Cohorts: following the customers who arrived together, month by month.

A single retention number is an average over people who joined at
very different times, which hides the thing anyone actually wants
to know: whether the customers arriving now stay longer than the
ones who arrived last year. A cohort analysis groups customers by
the period they joined and follows each group forward, so
improvement or decay in the product shows up as a difference
between the rows rather than being averaged into one figure that
never moves. This module builds that table. Retention is measured
against the cohort's own starting size, not against the previous
period, because chaining period-over-period rates compounds
rounding and makes a cohort that recovers look like one that never
fell. A customer who leaves and returns counts as retained in the
period they were active, since the table describes activity rather
than an unbroken subscription, and the module says so rather than
leaving a reader to guess which definition produced the number. A
period with no cohort returns no row instead of a zero, because a
zero implies a cohort that all left, which is a very different
fact from a month with no signups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused


@dataclass
class CohortTable:
    cohorts: dict[str, set[str]] = field(default_factory=dict)
    activity: dict[tuple[str, int], set[str]] = field(default_factory=dict)

    def enroll(self, cohort: str, customer_id: str) -> None:
        if not cohort.strip() or not customer_id.strip():
            raise Refused("a cohort and a customer both need identifiers")
        for existing, members in self.cohorts.items():
            if customer_id in members and existing != cohort:
                raise Refused(
                    f"{customer_id!r} is already in cohort {existing!r}; a "
                    "customer joins once or the table double-counts them"
                )
        self.cohorts.setdefault(cohort, set()).add(customer_id)

    def record_activity(self, cohort: str, period: int, customer_id: str) -> None:
        if cohort not in self.cohorts:
            raise Refused(f"there is no cohort {cohort!r}")
        if customer_id not in self.cohorts[cohort]:
            raise Refused(
                f"{customer_id!r} is not a member of cohort {cohort!r}"
            )
        if period < 0:
            raise Refused("a cohort period is not negative")
        self.activity.setdefault((cohort, period), set()).add(customer_id)

    def size(self, cohort: str) -> int:
        if cohort not in self.cohorts:
            raise Refused(f"there is no cohort {cohort!r}")
        return len(self.cohorts[cohort])

    def active(self, cohort: str, period: int) -> int:
        return len(self.activity.get((cohort, period), set()))

    def retention(self, cohort: str, period: int) -> Fraction | None:
        # Against the cohort's own starting size, never chained period over
        # period, so a cohort that dips and recovers reads as recovered.
        base = self.size(cohort)
        if base == 0:
            return None
        return Fraction(self.active(cohort, period), base)

    def row(self, cohort: str, periods: int) -> list[Fraction | None]:
        return [self.retention(cohort, period) for period in range(periods)]

    def table(self, periods: int) -> dict[str, list[Fraction | None]]:
        return {
            cohort: self.row(cohort, periods) for cohort in sorted(self.cohorts)
        }

    def cohort_names(self) -> list[str]:
        return sorted(self.cohorts)

    def improving(self, earlier: str, later: str, period: int) -> bool | None:
        first = self.retention(earlier, period)
        second = self.retention(later, period)
        if first is None or second is None:
            return None
        return second > first
