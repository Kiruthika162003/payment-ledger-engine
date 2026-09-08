"""The audit log: a hash-chained record where a changed entry cannot hide.

An audit log that can be edited is not an audit log, it is a
suggestion. The cheap and effective defence is a hash chain: each
record carries a digest computed over its own contents and the
digest of the record before it, so changing any record changes its
digest, which breaks the link the next record depends on, and the
break propagates to the end. Someone who alters a record must
recompute every digest after it, which is exactly the work an
attacker with only database access cannot do unnoticed if the tip
digest was ever written down or shipped elsewhere. This module
implements that chain and, more importantly, the verifier, since a
chain nobody checks provides no assurance at all: verification
walks from the genesis record forward, recomputing each digest, and
reports the index of the first record that does not match rather
than a bare false, because knowing where the tampering starts is
what makes the finding actionable. Records are append-only by
construction; the log offers no method to modify one, so the only
way to falsify it is to reach past this class entirely.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field

from mint.errors import Refused

GENESIS = "0" * 64


@dataclass(frozen=True)
class AuditRecord:
    index: int
    at: datetime.datetime
    actor: str
    action: str
    detail: str
    previous: str
    digest: str

    def recompute(self) -> str:
        return digest_for(
            self.index, self.at, self.actor, self.action, self.detail, self.previous
        )


def digest_for(
    index: int,
    at: datetime.datetime,
    actor: str,
    action: str,
    detail: str,
    previous: str,
) -> str:
    payload = "\x1f".join(
        [str(index), at.isoformat(), actor, action, detail, previous]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class AuditLog:
    records: list[AuditRecord] = field(default_factory=list)

    def tip(self) -> str:
        return self.records[-1].digest if self.records else GENESIS

    def append(
        self, actor: str, action: str, detail: str, at: datetime.datetime
    ) -> AuditRecord:
        if not actor.strip():
            raise Refused("an audit record names the actor who caused it")
        if not action.strip():
            raise Refused("an audit record names the action taken")
        index = len(self.records)
        previous = self.tip()
        record = AuditRecord(
            index=index,
            at=at,
            actor=actor.strip(),
            action=action.strip(),
            detail=detail,
            previous=previous,
            digest=digest_for(index, at, actor.strip(), action.strip(), detail, previous),
        )
        self.records.append(record)
        return record

    def first_broken(self) -> int | None:
        expected_previous = GENESIS
        for position, record in enumerate(self.records):
            if record.previous != expected_previous:
                return position
            if record.digest != record.recompute():
                return position
            expected_previous = record.digest
        return None

    def verify(self) -> bool:
        return self.first_broken() is None

    def count(self) -> int:
        return len(self.records)

    def by_actor(self, actor: str) -> list[AuditRecord]:
        return [record for record in self.records if record.actor == actor]
