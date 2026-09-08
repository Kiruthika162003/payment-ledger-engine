"""Assay: the audit chain notices an altered record and says where.

A tamper-evident log is worth exactly as much as its verifier, so
the claim to measure is not that the log stores digests but that
changing a record is caught, and caught at the right place. This
assay builds a log, alters a record in the middle, and confirms the
verifier fails and names that index. It then does the harder case:
an attacker who alters a record and recomputes that record's own
digest, which is the obvious first attempt, and confirms the break
simply moves to the next record, whose stored link no longer
matches. That is the property the chain exists for, that a local
repair is not enough, and measuring it is the difference between
having a hash chain and having a verified one. The clean log is
measured too, since a verifier that reports tampering on an
untouched log would be useless in the opposite direction.
"""

from __future__ import annotations

import dataclasses
import datetime

from mint.assays.framework import Finding, assay
from mint.auditlog import AuditLog

AT = datetime.datetime(2026, 3, 1, 12, 0, 0)


def _log(count: int = 6) -> AuditLog:
    log = AuditLog()
    for index in range(count):
        log.append("clerk", "post", f"entry {index}", AT)
    return log


@assay("tamper", "does the audit chain catch an altered record at the right index")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    clean = _log()
    findings.append(Finding("an untouched log verifies", clean.verify(), True))
    findings.append(Finding("no break in a clean log", clean.first_broken(), None))

    edited = _log()
    edited.records[3] = dataclasses.replace(edited.records[3], detail="altered")
    findings.append(Finding("an edited record fails verification", edited.verify(), False))
    findings.append(Finding("the break is named at its index", edited.first_broken(), 3))

    repaired = _log()
    target = dataclasses.replace(repaired.records[2], detail="altered")
    repaired.records[2] = dataclasses.replace(target, digest=target.recompute())
    findings.append(
        Finding("a locally repaired digest moves the break onward", repaired.first_broken(), 3)
    )
    return findings
