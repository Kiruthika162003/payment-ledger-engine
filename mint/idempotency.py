"""Idempotency: a retried request posts once, and a reused key is caught.

Payments travel over networks that drop responses, so the client
that sent a charge and heard nothing will send it again, and a
ledger that posts both has double-billed a customer over a dropped
packet rather than a real second purchase. The remedy is an
idempotency key: the client attaches a unique key to the request,
and the server records the key with the result the first time and
returns that same result on every retry without doing the work
again. This module is that record. It stores each key alongside a
fingerprint of the request it first served, so a retry of the same
request replays the stored result, while a different request
arriving under a key already used is refused rather than served,
because a reused key almost always means a client bug and serving
it would let one key mask two distinct charges. The fingerprint is
a hash of the parts the caller declares significant, which keeps
the comparison honest without storing the whole request, and the
store never expires a key on its own, since forgetting a key is
exactly how the double-post it was built to prevent creeps back
in.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mint.errors import Refused


def fingerprint(*parts: object) -> str:
    joined = "\x1f".join(repr(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


@dataclass
class IdempotencyStore:
    records: dict[str, tuple[str, Any]] = field(default_factory=dict)

    def seen(self, key: str) -> bool:
        return key in self.records

    def result(self, key: str) -> Any:
        if key not in self.records:
            raise Refused(f"idempotency key {key!r} has no recorded result")
        return self.records[key][1]

    def execute(self, key: str, request_fingerprint: str, produce: Callable[[], Any]) -> Any:
        if not key.strip():
            raise Refused("an idempotency key cannot be empty")
        if key in self.records:
            stored_fingerprint, stored_result = self.records[key]
            if stored_fingerprint != request_fingerprint:
                raise Refused(
                    f"idempotency key {key!r} was already used for a different "
                    "request; a reused key almost always means a client bug"
                )
            return stored_result
        result = produce()
        self.records[key] = (request_fingerprint, result)
        return result

    def forget(self, key: str) -> None:
        # Offered for tests and administrative replay only; production code
        # keeps keys, since forgetting one reopens the double-post window.
        self.records.pop(key, None)
