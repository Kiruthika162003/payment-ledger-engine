from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.idempotency import IdempotencyStore, fingerprint


class TestReplay:
    def test_a_retry_replays_without_rerunning(self):
        store = IdempotencyStore()
        calls = []

        def produce():
            calls.append(1)
            return "posted"

        key = "req-1"
        fp = fingerprint("charge", 1000, "USD")
        first = store.execute(key, fp, produce)
        second = store.execute(key, fp, produce)
        assert first == second == "posted"
        assert len(calls) == 1

    def test_a_reused_key_for_a_different_request_is_refused(self):
        store = IdempotencyStore()
        store.execute("req-1", fingerprint("a"), lambda: 1)
        with pytest.raises(Refused) as caught:
            store.execute("req-1", fingerprint("b"), lambda: 2)
        assert "different" in str(caught.value)

    def test_an_empty_key_is_refused(self):
        with pytest.raises(Refused):
            IdempotencyStore().execute("  ", fingerprint("a"), lambda: 1)


class TestQueries:
    def test_seen_and_result(self):
        store = IdempotencyStore()
        store.execute("k", fingerprint("x"), lambda: 42)
        assert store.seen("k")
        assert store.result("k") == 42

    def test_result_of_an_unknown_key_is_refused(self):
        with pytest.raises(Refused):
            IdempotencyStore().result("nope")

    def test_forget_reopens_the_key(self):
        store = IdempotencyStore()
        store.execute("k", fingerprint("x"), lambda: 1)
        store.forget("k")
        assert not store.seen("k")


class TestFingerprint:
    def test_same_parts_same_fingerprint(self):
        assert fingerprint("charge", 100, "USD") == fingerprint("charge", 100, "USD")

    def test_different_parts_differ(self):
        assert fingerprint("charge", 100, "USD") != fingerprint("charge", 101, "USD")
