"""Price books: which price applies, to whom, in what currency, on what date.

A product does not have a price; it has prices, one per currency,
per customer segment, and per period, and picking the wrong one is
a billing error nobody catches until a customer does. This module
resolves a price by the specificity rule real pricing systems use:
a price for this exact customer beats a price for their segment,
which beats the list price, and among candidates of equal
specificity the one in force on the date wins. Effective dating is
inclusive of the start and exclusive of the end, which is the
convention that lets a new price start the day the old one stops
without a gap or an overlap on the changeover date, the two failure
modes that produce either no price or two prices at midnight. A
lookup that finds nothing refuses by name rather than falling back
to zero, because a free sale caused by a missing price is worse
than a failed one. Prices are stored per currency rather than
converted on the fly, since a business sets its euro price
deliberately rather than by yesterday's rate.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class PriceEntry:
    sku: str
    price: Money
    starts: datetime.date
    ends: datetime.date | None = None
    customer_id: str | None = None
    segment: str | None = None

    def __post_init__(self) -> None:
        if self.ends is not None and self.ends <= self.starts:
            raise Refused(
                f"the price for {self.sku!r} ends on or before it starts"
            )
        if self.customer_id is not None and self.segment is not None:
            raise Refused(
                "a price entry targets a customer or a segment, not both"
            )

    def specificity(self) -> int:
        if self.customer_id is not None:
            return 2
        if self.segment is not None:
            return 1
        return 0

    def in_force(self, on: datetime.date) -> bool:
        # Start inclusive, end exclusive: a new price begins the day the old
        # one stops, with no gap and no overlap at the changeover.
        if on < self.starts:
            return False
        return self.ends is None or on < self.ends


@dataclass
class PriceBook:
    entries: list[PriceEntry] = field(default_factory=list)

    def add(self, entry: PriceEntry) -> PriceEntry:
        self.entries.append(entry)
        return entry

    def candidates(
        self,
        sku: str,
        currency: str,
        on: datetime.date,
        customer_id: str | None = None,
        segment: str | None = None,
    ) -> list[PriceEntry]:
        found: list[PriceEntry] = []
        for entry in self.entries:
            if entry.sku != sku or entry.price.currency != currency.upper():
                continue
            if not entry.in_force(on):
                continue
            if entry.customer_id is not None and entry.customer_id != customer_id:
                continue
            if entry.segment is not None and entry.segment != segment:
                continue
            found.append(entry)
        return found

    def price_for(
        self,
        sku: str,
        currency: str,
        on: datetime.date,
        customer_id: str | None = None,
        segment: str | None = None,
    ) -> Money:
        found = self.candidates(sku, currency, on, customer_id, segment)
        if not found:
            raise Refused(
                f"no {currency.upper()} price for {sku!r} is in force on "
                f"{on.isoformat()}; a free sale is worse than a failed one"
            )
        best = max(found, key=lambda entry: (entry.specificity(), entry.starts))
        return best.price

    def has_price(
        self,
        sku: str,
        currency: str,
        on: datetime.date,
        customer_id: str | None = None,
        segment: str | None = None,
    ) -> bool:
        return bool(self.candidates(sku, currency, on, customer_id, segment))

    def skus(self) -> list[str]:
        return sorted({entry.sku for entry in self.entries})
