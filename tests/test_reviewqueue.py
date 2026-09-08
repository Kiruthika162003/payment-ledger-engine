from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.reviewqueue import ItemState, ReviewItem, ReviewQueue

NOW = datetime.datetime(2026, 1, 1, 12, 0)


def _item(item_id, priority, created_offset=0, due_offset=60):
    created = NOW + datetime.timedelta(minutes=created_offset)
    return ReviewItem(
        id=item_id,
        subject=f"txn-{item_id}",
        priority=priority,
        created=created,
        due=created + datetime.timedelta(minutes=due_offset),
    )


def _queue() -> ReviewQueue:
    # The low item is older but has plenty of time left; giving it the
    # default sixty-minute deadline would make it breaching and it would
    # correctly outrank the high-priority one.
    queue = ReviewQueue()
    queue.add(_item("low", 1, created_offset=-100, due_offset=300))
    queue.add(_item("high", 9, created_offset=-10))
    return queue


class TestOrdering:
    def test_priority_beats_age_when_nothing_is_breaching(self):
        queue = _queue()
        assert queue.next_item(NOW).id == "high"

    def test_a_breaching_item_jumps_the_queue(self):
        queue = ReviewQueue()
        queue.add(_item("high", 9, created_offset=-10))
        queue.add(_item("stale", 1, created_offset=-500, due_offset=60))
        assert queue.next_item(NOW).id == "stale"

    def test_among_equals_the_oldest_goes_first(self):
        queue = ReviewQueue()
        queue.add(_item("newer", 5, created_offset=-5))
        queue.add(_item("older", 5, created_offset=-50))
        assert queue.next_item(NOW).id == "older"

    def test_an_empty_queue_offers_nothing(self):
        assert ReviewQueue().next_item(NOW) is None


class TestClaiming:
    def test_a_claimed_item_leaves_the_available_list(self):
        queue = _queue()
        queue.claim("high", "alice", NOW)
        assert queue.next_item(NOW).id == "low"

    def test_a_second_reviewer_is_refused(self):
        queue = _queue()
        queue.claim("high", "alice", NOW)
        with pytest.raises(Refused) as caught:
            queue.claim("high", "bob", NOW)
        assert "two approvals of one payment" in str(caught.value)

    def test_an_expired_claim_returns_the_item(self):
        queue = _queue()
        queue.claim("high", "alice", NOW, hold_minutes=15)
        later = NOW + datetime.timedelta(minutes=30)
        assert queue.next_item(later).id == "high"


class TestResolution:
    def test_approving_closes_the_item(self):
        queue = _queue()
        item = queue.resolve("high", "alice", True, "verified by phone")
        assert item.state is ItemState.APPROVED
        assert item.resolved_by == "alice"

    def test_rejecting_closes_it_too(self):
        queue = _queue()
        assert queue.resolve("high", "alice", False, "no answer").state is ItemState.REJECTED

    def test_resolving_twice_is_refused(self):
        queue = _queue()
        queue.resolve("high", "alice", True, "ok")
        with pytest.raises(Refused):
            queue.resolve("high", "bob", False, "changed my mind")

    def test_an_anonymous_resolution_is_refused(self):
        with pytest.raises(Refused) as caught:
            _queue().resolve("high", "  ", True, "ok")
        assert "not a control anyone can rely on" in str(caught.value)

    def test_a_resolution_without_a_note_is_refused(self):
        with pytest.raises(Refused):
            _queue().resolve("high", "alice", True, "   ")


class TestQueueState:
    def test_breaching_items_are_listed(self):
        queue = ReviewQueue()
        queue.add(_item("stale", 1, created_offset=-500, due_offset=60))
        assert [item.id for item in queue.breaching(NOW)] == ["stale"]

    def test_open_count_falls_as_items_resolve(self):
        queue = _queue()
        assert queue.open_count() == 2
        queue.resolve("high", "alice", True, "ok")
        assert queue.open_count() == 1

    def test_a_duplicate_id_is_refused(self):
        queue = _queue()
        with pytest.raises(Refused):
            queue.add(_item("high", 3))

    def test_an_item_due_before_it_arrived_is_refused(self):
        queue = ReviewQueue()
        with pytest.raises(Refused):
            queue.add(_item("bad", 1, due_offset=-10))
