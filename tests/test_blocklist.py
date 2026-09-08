from __future__ import annotations

import datetime

import pytest

from mint.blocklist import Blocklist
from mint.errors import Refused

JAN1 = datetime.date(2026, 1, 1)
JAN15 = datetime.date(2026, 1, 15)
FEB1 = datetime.date(2026, 2, 1)


def _list() -> Blocklist:
    blocklist = Blocklist("sanctions")
    blocklist.add("acct-666", "failed verification", "risk-team", JAN1, expires_on=JAN15)
    blocklist.add("acct-999", "confirmed fraud", "risk-team", JAN1)
    return blocklist


class TestBlocking:
    def test_an_active_block_matches(self):
        assert _list().is_blocked("acct-666", JAN1)

    def test_the_reason_is_available(self):
        assert _list().reason_for("acct-999", FEB1) == "confirmed fraud"

    def test_the_guard_refuses_with_the_reason(self):
        with pytest.raises(Refused) as caught:
            _list().guard("acct-999", FEB1)
        assert "confirmed fraud" in str(caught.value)

    def test_an_unblocked_subject_passes_the_guard(self):
        _list().guard("acct-111", FEB1)


class TestExpiry:
    def test_a_temporary_block_lapses(self):
        blocklist = _list()
        assert blocklist.is_blocked("acct-666", JAN15)
        assert not blocklist.is_blocked("acct-666", FEB1)

    def test_a_permanent_block_does_not(self):
        assert _list().is_blocked("acct-999", datetime.date(2030, 1, 1))

    def test_permanent_entries_are_listed(self):
        assert [e.subject for e in _list().permanent_entries()] == ["acct-999"]

    def test_a_block_is_not_active_before_it_was_added(self):
        assert not _list().is_blocked("acct-999", datetime.date(2025, 1, 1))


class TestLifting:
    def test_lifting_takes_effect_immediately(self):
        blocklist = _list()
        blocklist.lift("acct-999", FEB1)
        assert not blocklist.is_blocked("acct-999", FEB1)

    def test_the_history_survives_a_lift(self):
        blocklist = _list()
        blocklist.lift("acct-999", FEB1)
        assert any(e.subject == "acct-999" for e in blocklist.entries)

    def test_lifting_nothing_is_refused(self):
        with pytest.raises(Refused):
            _list().lift("acct-111", FEB1)


class TestExactMatching:
    def test_a_similar_name_does_not_match(self):
        assert not _list().is_blocked("acct-9990", FEB1)


class TestRefusals:
    def test_a_block_needs_a_reason(self):
        with pytest.raises(Refused) as caught:
            Blocklist("x").add("s", "  ", "who", JAN1)
        assert "outlives everyone" in str(caught.value)

    def test_a_block_needs_an_author(self):
        with pytest.raises(Refused):
            Blocklist("x").add("s", "reason", "  ", JAN1)

    def test_expiry_before_addition_is_refused(self):
        with pytest.raises(Refused):
            Blocklist("x").add("s", "r", "w", FEB1, expires_on=JAN1)
