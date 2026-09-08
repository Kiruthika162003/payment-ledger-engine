"""Aging: sorting what is owed by how overdue it is, edges named exactly.

An aging report groups the amounts owed, receivable or payable, by
how long they have been outstanding, and it is the first thing a
credit manager reads because a dollar ninety days late is worth far
less than a dollar not yet due. The value of the report is entirely
in getting the bucket edges right, and off-by-one edges are the
classic bug: does a thirty-day-old invoice fall in the first bucket
or the second. This module fixes the convention explicitly and
tests it. Days overdue is the as-of date minus the due date; an
item with zero or fewer days overdue is current, not yet a
problem, and a positive count falls in the first bucket whose upper
edge it does not exceed, so with edges at thirty, sixty, and ninety
an item thirty days late is in the one-to-thirty bucket, thirty-one
days late in the next, and anything past ninety in the final
open-ended bucket. Amounts are summed per bucket in a single
currency, since aging a mix of currencies into one column produces
a total no one can collect, and the per-item bucket is available so
a caller can list the specific invoices behind a worrying column
rather than only its total.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from mint.errors import CurrencyMismatch, Refused
from mint.money import Money

DEFAULT_EDGES = (30, 60, 90)


@dataclass(frozen=True)
class AgingItem:
    id: str
    amount: Money
    due: datetime.date


@dataclass(frozen=True)
class AgingReport:
    currency: str
    as_of: datetime.date
    buckets: tuple[tuple[str, int], ...]
    placement: dict[str, str]

    def total(self) -> Money:
        return Money.from_minor(sum(units for _, units in self.buckets), self.currency)

    def bucket_total(self, label: str) -> Money:
        for name, units in self.buckets:
            if name == label:
                return Money.from_minor(units, self.currency)
        raise Refused(f"there is no aging bucket named {label!r}")

    def bucket_of(self, item_id: str) -> str:
        if item_id not in self.placement:
            raise Refused(f"item {item_id!r} was not in the aging run")
        return self.placement[item_id]


def _labels(edges: tuple[int, ...]) -> list[str]:
    labels = ["current"]
    lower = 1
    for edge in edges:
        labels.append(f"{lower}-{edge}")
        lower = edge + 1
    labels.append(f">{edges[-1]}")
    return labels


def _bucket_for(days_overdue: int, edges: tuple[int, ...]) -> str:
    if days_overdue <= 0:
        return "current"
    lower = 1
    for edge in edges:
        if days_overdue <= edge:
            return f"{lower}-{edge}"
        lower = edge + 1
    return f">{edges[-1]}"


def age(
    items: list[AgingItem],
    as_of: datetime.date,
    currency: str,
    edges: tuple[int, ...] = DEFAULT_EDGES,
) -> AgingReport:
    currency = currency.upper()
    if list(edges) != sorted(edges) or len(set(edges)) != len(edges):
        raise Refused("aging edges must be strictly increasing")
    totals = dict.fromkeys(_labels(edges), 0)
    placement: dict[str, str] = {}
    for item in items:
        if item.amount.currency != currency:
            raise CurrencyMismatch(
                f"item {item.id!r} is in {item.amount.currency}, not {currency}; "
                "age one currency at a time"
            )
        days = (as_of - item.due).days
        label = _bucket_for(days, edges)
        totals[label] += item.amount.units
        placement[item.id] = label
    return AgingReport(
        currency=currency,
        as_of=as_of,
        buckets=tuple(totals.items()),
        placement=placement,
    )
