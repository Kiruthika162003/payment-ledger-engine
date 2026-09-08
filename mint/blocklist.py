"""Blocklists: refusing to deal with a party, for a reason, and not forever by accident.

A blocklist is a small database with unusually high stakes: a wrong
entry silently stops a legitimate customer from paying, and nobody
finds out until they complain. So every entry here carries a reason
and the person who added it, and entries can expire, because most
blocks are responses to a moment, a burst of fraud attempts or a
failed verification, and leaving them permanent by default turns a
temporary control into an unexplained permanent ban that outlives
everyone who remembers why. Lookups are exact rather than fuzzy, on
the principle that a blocklist should never guess: matching a
similar name is how an innocent person with a common name gets
frozen out, and a system that wants fuzzy matching should put it in
a review queue rather than an automatic refusal. The list reports
whether a block is active as of a date rather than storing a
boolean that has to be swept, so an expired block simply stops
matching without a job having to run, and the history of why
someone was blocked stays readable afterward.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused


@dataclass(frozen=True)
class BlockEntry:
    subject: str
    reason: str
    added_by: str
    added_on: datetime.date
    expires_on: datetime.date | None = None

    def is_active(self, as_of: datetime.date) -> bool:
        if as_of < self.added_on:
            return False
        return self.expires_on is None or as_of <= self.expires_on

    def is_permanent(self) -> bool:
        return self.expires_on is None


@dataclass
class Blocklist:
    name: str
    entries: list[BlockEntry] = field(default_factory=list)

    def add(
        self,
        subject: str,
        reason: str,
        added_by: str,
        added_on: datetime.date,
        expires_on: datetime.date | None = None,
    ) -> BlockEntry:
        if not subject.strip():
            raise Refused("a block needs a subject")
        if not reason.strip():
            raise Refused(
                "a block needs a reason; an unexplained block outlives everyone "
                "who remembers why it was added"
            )
        if not added_by.strip():
            raise Refused("a block names who added it")
        if expires_on is not None and expires_on < added_on:
            raise Refused("a block cannot expire before it is added")
        entry = BlockEntry(
            subject.strip(), reason.strip(), added_by.strip(), added_on, expires_on
        )
        self.entries.append(entry)
        return entry

    def active_entries(self, as_of: datetime.date) -> list[BlockEntry]:
        return [entry for entry in self.entries if entry.is_active(as_of)]

    def is_blocked(self, subject: str, as_of: datetime.date) -> bool:
        # Exact match only: a fuzzy blocklist freezes out innocent people who
        # share a name, and that belongs in a review queue, not a refusal.
        return any(
            entry.subject == subject.strip() and entry.is_active(as_of)
            for entry in self.entries
        )

    def reason_for(self, subject: str, as_of: datetime.date) -> str:
        for entry in self.active_entries(as_of):
            if entry.subject == subject.strip():
                return entry.reason
        raise Refused(f"{subject!r} is not blocked on {as_of.isoformat()}")

    def guard(self, subject: str, as_of: datetime.date) -> None:
        if self.is_blocked(subject, as_of):
            raise Refused(
                f"{subject!r} is on the {self.name} blocklist: "
                f"{self.reason_for(subject, as_of)}"
            )

    def lift(self, subject: str, on: datetime.date) -> int:
        # Expiry is inclusive, so a lift dated today must set the last active
        # day to yesterday for the block to stop applying immediately.
        last_active = on - datetime.timedelta(days=1)
        lifted = 0
        for index, entry in enumerate(self.entries):
            if entry.subject == subject.strip() and entry.is_active(on):
                self.entries[index] = BlockEntry(
                    entry.subject,
                    entry.reason,
                    entry.added_by,
                    entry.added_on,
                    last_active,
                )
                lifted += 1
        if lifted == 0:
            raise Refused(f"{subject!r} has no active block to lift")
        return lifted

    def permanent_entries(self) -> list[BlockEntry]:
        return [entry for entry in self.entries if entry.is_permanent()]
