"""A review queue: the work a machine would not decide, ordered so the right item is next.

Anything a rule cannot settle lands in front of a person, and the
queue that holds those items decides whether the control works. Two
failures are common. A queue ordered purely by arrival lets a
high-value case sit behind a hundred trivial ones; a queue ordered
purely by value never clears the small items and they age until
their deadline passes. This module orders by breach first, then by
priority, then by age, so an item about to miss its deadline jumps
ahead regardless of size, and among items with time left the
important ones go first while the old ones still climb. Items are
claimed rather than merely read, because two reviewers working the
same case is wasted effort and, worse, two independent approvals of
one payment. A claim expires so a reviewer who closes their laptop
does not strand the item forever. Every decision records who made
it and why, since the queue exists to produce an audit trail as much
as to produce decisions, and a resolution without a reviewer's name
is not a control anyone can rely on.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from mint.errors import Refused


class ItemState(Enum):
    WAITING = "waiting"
    CLAIMED = "claimed"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ReviewItem:
    id: str
    subject: str
    priority: int
    created: datetime.datetime
    due: datetime.datetime
    state: ItemState = ItemState.WAITING
    claimed_by: str | None = None
    claim_expires: datetime.datetime | None = None
    resolved_by: str | None = None
    resolution_note: str = ""

    def is_open(self) -> bool:
        return self.state in (ItemState.WAITING, ItemState.CLAIMED)

    def is_breaching(self, now: datetime.datetime) -> bool:
        return self.is_open() and now >= self.due

    def claim_is_live(self, now: datetime.datetime) -> bool:
        if self.state is not ItemState.CLAIMED or self.claim_expires is None:
            return False
        return now < self.claim_expires

    def age_seconds(self, now: datetime.datetime) -> float:
        return (now - self.created).total_seconds()


@dataclass
class ReviewQueue:
    items: list[ReviewItem] = field(default_factory=list)

    def add(self, item: ReviewItem) -> ReviewItem:
        if any(existing.id == item.id for existing in self.items):
            raise Refused(f"item {item.id!r} is already in the queue")
        if item.due < item.created:
            raise Refused(f"item {item.id!r} is due before it arrived")
        self.items.append(item)
        return item

    def open_items(self, now: datetime.datetime) -> list[ReviewItem]:
        available = [
            item
            for item in self.items
            if item.is_open() and not item.claim_is_live(now)
        ]
        # Breaching first, then priority, then oldest: a deadline outranks
        # value, and among items with time left the old ones still climb.
        return sorted(
            available,
            key=lambda item: (
                not item.is_breaching(now),
                -item.priority,
                item.created,
            ),
        )

    def next_item(self, now: datetime.datetime) -> ReviewItem | None:
        available = self.open_items(now)
        return available[0] if available else None

    def claim(
        self, item_id: str, reviewer: str, now: datetime.datetime, hold_minutes: int = 15
    ) -> ReviewItem:
        item = self.get(item_id)
        if not item.is_open():
            raise Refused(f"item {item_id!r} is already {item.state.value}")
        if item.claim_is_live(now):
            raise Refused(
                f"item {item_id!r} is claimed by {item.claimed_by!r}; two "
                "reviewers on one case is two approvals of one payment"
            )
        item.state = ItemState.CLAIMED
        item.claimed_by = reviewer
        item.claim_expires = now + datetime.timedelta(minutes=hold_minutes)
        return item

    def resolve(
        self, item_id: str, reviewer: str, approved: bool, note: str
    ) -> ReviewItem:
        item = self.get(item_id)
        if not item.is_open():
            raise Refused(f"item {item_id!r} is already {item.state.value}")
        if not reviewer.strip():
            raise Refused(
                "a resolution names its reviewer; an anonymous decision is not "
                "a control anyone can rely on"
            )
        if not note.strip():
            raise Refused("a resolution records why the decision was made")
        item.state = ItemState.APPROVED if approved else ItemState.REJECTED
        item.resolved_by = reviewer.strip()
        item.resolution_note = note.strip()
        return item

    def get(self, item_id: str) -> ReviewItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise Refused(f"there is no review item {item_id!r}")

    def breaching(self, now: datetime.datetime) -> list[ReviewItem]:
        return [item for item in self.items if item.is_breaching(now)]

    def open_count(self) -> int:
        return sum(1 for item in self.items if item.is_open())
