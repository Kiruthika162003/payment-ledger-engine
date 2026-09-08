from __future__ import annotations

import dataclasses
import datetime

import pytest

from mint.auditlog import GENESIS, AuditLog
from mint.errors import Refused

AT = datetime.datetime(2026, 1, 1, 9, 0, 0)


def _log() -> AuditLog:
    log = AuditLog()
    for index in range(5):
        log.append("clerk", "post", f"entry {index}", AT)
    return log


class TestChain:
    def test_the_first_record_links_to_genesis(self):
        log = _log()
        assert log.records[0].previous == GENESIS

    def test_each_record_links_to_the_one_before(self):
        log = _log()
        for earlier, later in zip(log.records, log.records[1:], strict=False):
            assert later.previous == earlier.digest

    def test_a_fresh_log_verifies(self):
        assert _log().verify()
        assert _log().first_broken() is None

    def test_the_tip_is_the_last_digest(self):
        log = _log()
        assert log.tip() == log.records[-1].digest


class TestTampering:
    def test_editing_a_record_is_detected(self):
        log = _log()
        log.records[2] = dataclasses.replace(log.records[2], detail="altered")
        assert not log.verify()

    def test_the_verifier_names_where_it_broke(self):
        log = _log()
        log.records[2] = dataclasses.replace(log.records[2], detail="altered")
        assert log.first_broken() == 2

    def test_recomputing_a_digest_without_relinking_still_breaks_the_chain(self):
        log = _log()
        tampered = dataclasses.replace(log.records[1], detail="altered")
        log.records[1] = dataclasses.replace(tampered, digest=tampered.recompute())
        # Its own digest now matches, but the next record's link does not.
        assert log.first_broken() == 2


class TestAppend:
    def test_records_are_indexed_in_order(self):
        log = _log()
        assert [r.index for r in log.records] == [0, 1, 2, 3, 4]
        assert log.count() == 5

    def test_records_can_be_filtered_by_actor(self):
        log = _log()
        log.append("auditor", "review", "quarterly", AT)
        assert len(log.by_actor("auditor")) == 1
        assert len(log.by_actor("clerk")) == 5

    def test_an_actorless_record_is_refused(self):
        with pytest.raises(Refused):
            AuditLog().append("  ", "post", "detail", AT)

    def test_an_actionless_record_is_refused(self):
        with pytest.raises(Refused):
            AuditLog().append("clerk", "", "detail", AT)
