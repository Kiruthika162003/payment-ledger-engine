"""Dimensions: slicing the ledger by department, project, or region.

An account tells you what kind of thing happened; a dimension tells
you where. The same rent expense belongs to a department, a
project, and a location at once, and a business that wants to know
which project is losing money needs the ledger sliced by that
dimension rather than by account. This module tags entries with
dimension values and reports totals sliced by them. The rule that
keeps the slices honest is completeness: every posting to a
dimensioned account must carry a value for that dimension, because
a slice that silently drops untagged postings shows totals that do
not sum to the account balance and quietly hides the very spending
someone is looking for. So the module reports untagged amounts as
an explicit unallocated bucket rather than omitting them, and the
sliced totals always add back to the account total. Slicing by two
dimensions at once produces a cross-tab, and because a posting
carries one value per dimension the cross-tab also foots exactly,
which is the property that makes it safe to publish.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.entry import Entry
from mint.errors import Refused
from mint.money import Money

UNALLOCATED = "(unallocated)"


@dataclass
class DimensionSet:
    name: str
    values: set[str] = field(default_factory=set)
    tags: dict[str, str] = field(default_factory=dict)

    def declare(self, value: str) -> str:
        if not value.strip():
            raise Refused(f"a {self.name} value cannot be blank")
        self.values.add(value.strip())
        return value.strip()

    def tag(self, entry_ref: str, value: str) -> None:
        if value not in self.values:
            raise Refused(
                f"{value!r} is not a declared {self.name}; declare it before "
                "tagging entries with it"
            )
        self.tags[entry_ref] = value

    def value_for(self, entry_ref: str) -> str:
        return self.tags.get(entry_ref, UNALLOCATED)


def slice_by(
    entries: list[Entry],
    dimension: DimensionSet,
    account: str,
    currency: str,
) -> dict[str, Money]:
    totals: dict[str, int] = {}
    for entry in entries:
        postings = entry.postings_for(account)
        if not postings:
            continue
        value = dimension.value_for(entry.ref)
        for posting in postings:
            if posting.currency != currency:
                continue
            signed = posting.debit_units() - posting.credit_units()
            totals[value] = totals.get(value, 0) + signed
    return {key: Money.from_minor(units, currency) for key, units in totals.items()}


def slice_total(sliced: dict[str, Money], currency: str) -> Money:
    total = Money.zero(currency)
    for value in sliced.values():
        total = total + value
    return total


def cross_tab(
    entries: list[Entry],
    rows: DimensionSet,
    columns: DimensionSet,
    account: str,
    currency: str,
) -> dict[tuple[str, str], Money]:
    totals: dict[tuple[str, str], int] = {}
    for entry in entries:
        postings = entry.postings_for(account)
        if not postings:
            continue
        key = (rows.value_for(entry.ref), columns.value_for(entry.ref))
        for posting in postings:
            if posting.currency != currency:
                continue
            signed = posting.debit_units() - posting.credit_units()
            totals[key] = totals.get(key, 0) + signed
    return {key: Money.from_minor(units, currency) for key, units in totals.items()}


def unallocated_share(sliced: dict[str, Money], currency: str) -> Money:
    return sliced.get(UNALLOCATED, Money.zero(currency))
