"""Mapping one chart to another: many old accounts into one new, without losing any.

Migrating or consolidating means translating one chart of accounts
into another, and the translation is almost never one to one.
Several old accounts collapse into one new one, an old account
splits across two, and a few have no home at all. The failure that
matters is silent loss: an old account with no mapping whose
balance simply does not appear in the new ledger, which nobody
notices because the new ledger still balances without it. So this
module treats completeness as the property to prove rather than
assume. It reports the unmapped source accounts by name, refuses to
call a mapping complete while any remain, and confirms that
translating a set of balances preserves their total exactly. A
split mapping distributes by weights using the cent-conserving
allocation, so an account divided between two targets contributes
its whole balance and not a cent more or less.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import allocate


@dataclass(frozen=True)
class Mapping:
    source: str
    targets: tuple[tuple[str, Fraction], ...]

    def __post_init__(self) -> None:
        if not self.targets:
            raise Refused(f"the mapping for {self.source!r} names no target")
        if any(weight <= 0 for _, weight in self.targets):
            raise Refused("a mapping weight is positive")

    def is_split(self) -> bool:
        return len(self.targets) > 1

    def distribute(self, amount: Money) -> list[tuple[str, Money]]:
        if len(self.targets) == 1:
            return [(self.targets[0][0], amount)]
        weights = [weight for _, weight in self.targets]
        shares = allocate(amount, weights)
        return [
            (name, share)
            for (name, _), share in zip(self.targets, shares, strict=True)
        ]


@dataclass
class ChartMapping:
    currency: str
    mappings: dict[str, Mapping] = field(default_factory=dict)

    def map_one(self, source: str, target: str) -> Mapping:
        return self.map_many(source, [(target, Fraction(1))])

    def map_many(
        self, source: str, targets: list[tuple[str, Fraction]]
    ) -> Mapping:
        if source in self.mappings:
            raise Refused(f"account {source!r} is already mapped")
        mapping = Mapping(source, tuple(targets))
        self.mappings[source] = mapping
        return mapping

    def unmapped(self, sources: list[str]) -> list[str]:
        # Named rather than dropped: the new ledger still balances without
        # them, which is exactly why nobody notices.
        return sorted(source for source in sources if source not in self.mappings)

    def is_complete(self, sources: list[str]) -> bool:
        return not self.unmapped(sources)

    def targets(self) -> list[str]:
        found: set[str] = set()
        for mapping in self.mappings.values():
            for name, _ in mapping.targets:
                found.add(name)
        return sorted(found)

    def collapsed(self) -> dict[str, list[str]]:
        buckets: dict[str, list[str]] = {}
        for mapping in self.mappings.values():
            for name, _ in mapping.targets:
                buckets.setdefault(name, []).append(mapping.source)
        return {name: sorted(sources) for name, sources in sorted(buckets.items())}

    def translate(self, balances: dict[str, Money]) -> dict[str, Money]:
        missing = self.unmapped(list(balances))
        if missing:
            raise Refused(
                f"these accounts have no mapping and their balances would "
                f"vanish: {missing}"
            )
        out: dict[str, int] = {}
        for source, amount in balances.items():
            if amount.currency != self.currency:
                raise Refused(
                    f"the balance for {source!r} is in {amount.currency}, not "
                    f"{self.currency}"
                )
            for target, share in self.mappings[source].distribute(amount):
                out[target] = out.get(target, 0) + share.units
        return {
            name: Money.from_minor(units, self.currency)
            for name, units in sorted(out.items())
        }

    def preserves_total(self, balances: dict[str, Money]) -> bool:
        before = Money.zero(self.currency)
        for amount in balances.values():
            before = before + amount
        after = Money.zero(self.currency)
        for amount in self.translate(balances).values():
            after = after + amount
        return before == after
