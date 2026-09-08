from __future__ import annotations

import datetime

import pytest

from mint.authorization import Authorization, HoldStatus
from mint.errors import InsufficientFunds, Refused
from mint.money import Money

CREATED = datetime.date(2026, 1, 1)
LATER = datetime.date(2026, 1, 10)
EXPIRY = datetime.date(2026, 1, 8)


def _auth(amount: str = "100.00", expires: datetime.date | None = None) -> Authorization:
    return Authorization("auth_1", Money.of(amount, "USD"), CREATED, expires=expires)


class TestCapture:
    def test_a_full_capture_closes_the_hold(self):
        auth = _auth()
        auth.capture(Money.of(100, "USD"), CREATED)
        assert auth.remaining().is_zero()
        assert auth.status(CREATED) is HoldStatus.CAPTURED

    def test_partial_captures_accumulate(self):
        auth = _auth()
        auth.capture(Money.of(30, "USD"), CREATED)
        auth.capture(Money.of(20, "USD"), CREATED)
        assert auth.captured_total() == Money.of(50, "USD")
        assert auth.remaining() == Money.of(50, "USD")
        assert auth.status(CREATED) is HoldStatus.PARTIALLY_CAPTURED

    def test_over_capture_names_the_gap(self):
        auth = _auth()
        auth.capture(Money.of(90, "USD"), CREATED)
        with pytest.raises(InsufficientFunds) as caught:
            auth.capture(Money.of(20, "USD"), CREATED)
        assert "still held" in str(caught.value)

    def test_a_fresh_hold_is_open(self):
        assert _auth().status(CREATED) is HoldStatus.OPEN


class TestVoid:
    def test_void_releases_the_remainder(self):
        auth = _auth()
        auth.capture(Money.of(40, "USD"), CREATED)
        released = auth.void(CREATED)
        assert released == Money.of(60, "USD")
        assert auth.status(CREATED) is HoldStatus.VOIDED

    def test_capturing_a_voided_hold_is_refused(self):
        auth = _auth()
        auth.void(CREATED)
        with pytest.raises(Refused) as caught:
            auth.capture(Money.of(10, "USD"), CREATED)
        assert "voided" in str(caught.value)

    def test_voiding_a_fully_captured_hold_is_refused(self):
        auth = _auth()
        auth.capture(Money.of(100, "USD"), CREATED)
        with pytest.raises(Refused) as caught:
            auth.void(CREATED)
        assert "nothing left to void" in str(caught.value)


class TestExpiry:
    def test_a_capture_after_expiry_is_refused(self):
        auth = _auth(expires=EXPIRY)
        with pytest.raises(Refused) as caught:
            auth.capture(Money.of(10, "USD"), LATER)
        assert "expired" in str(caught.value)

    def test_an_uncaptured_hold_reads_expired_after_the_date(self):
        auth = _auth(expires=EXPIRY)
        assert auth.status(LATER) is HoldStatus.EXPIRED

    def test_expiry_before_creation_is_refused(self):
        with pytest.raises(Refused):
            Authorization("x", Money.of(1, "USD"), CREATED, expires=datetime.date(2025, 1, 1))
