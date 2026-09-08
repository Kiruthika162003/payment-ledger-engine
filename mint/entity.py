"""Entities: separate legal books, and who owns how much of whom.

A group of companies keeps separate books because each company is a
separate legal person that files its own return, and the group
report is built from those books rather than replacing them. This
module holds the registry of entities and the ownership between
them, which is the structure consolidation needs. Ownership is a
fraction, and the distinction that matters is between control and
ownership: a parent holding sixty percent controls the subsidiary
and therefore consolidates all of its numbers, while owning only
sixty percent of them, so the forty percent belonging to others
appears as a minority interest rather than being netted away. That
is why this module keeps the fraction rather than a boolean, and
why it can answer both questions separately. Ownership cycles are
refused, since a structure where A owns B and B owns A has no
well-defined consolidation order and is almost always a data-entry
error rather than a real cross-holding. Each entity names its
functional currency, the currency it actually trades in, because
that is what decides which rate translates its statements later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused

CONTROL_THRESHOLD = Fraction(1, 2)


@dataclass(frozen=True)
class Entity:
    code: str
    name: str
    currency: str


@dataclass
class Group:
    entities: dict[str, Entity] = field(default_factory=dict)
    ownership: dict[tuple[str, str], Fraction] = field(default_factory=dict)

    def add(self, entity: Entity) -> Entity:
        if entity.code in self.entities:
            raise Refused(f"entity {entity.code!r} is already in the group")
        self.entities[entity.code] = entity
        return entity

    def get(self, code: str) -> Entity:
        if code not in self.entities:
            raise Refused(f"there is no entity {code!r} in the group")
        return self.entities[code]

    def own(self, parent: str, child: str, share: Fraction) -> Fraction:
        self.get(parent)
        self.get(child)
        if parent == child:
            raise Refused("an entity cannot own itself")
        if share <= 0 or share > 1:
            raise Refused("an ownership share is a fraction above zero and at most one")
        if self._would_cycle(parent, child):
            raise Refused(
                f"{child!r} already owns {parent!r} directly or indirectly; a "
                "cycle has no well-defined consolidation order"
            )
        self.ownership[(parent, child)] = share
        return share

    def _would_cycle(self, parent: str, child: str) -> bool:
        seen: set[str] = set()
        frontier = [child]
        while frontier:
            current = frontier.pop()
            if current == parent:
                return True
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(self.children_of(current))
        return False

    def children_of(self, parent: str) -> list[str]:
        return sorted(child for (owner, child) in self.ownership if owner == parent)

    def share_of(self, parent: str, child: str) -> Fraction:
        return self.ownership.get((parent, child), Fraction(0))

    def controls(self, parent: str, child: str) -> bool:
        return self.share_of(parent, child) > CONTROL_THRESHOLD

    def minority_share(self, parent: str, child: str) -> Fraction:
        return 1 - self.share_of(parent, child)

    def subsidiaries(self, parent: str) -> list[str]:
        found: list[str] = []
        frontier = self.children_of(parent)
        while frontier:
            current = frontier.pop()
            if current in found:
                continue
            found.append(current)
            frontier.extend(self.children_of(current))
        return sorted(found)

    def controlled_subsidiaries(self, parent: str) -> list[str]:
        return sorted(
            child for child in self.children_of(parent) if self.controls(parent, child)
        )

    def roots(self) -> list[str]:
        owned = {child for (_owner, child) in self.ownership}
        return sorted(code for code in self.entities if code not in owned)
