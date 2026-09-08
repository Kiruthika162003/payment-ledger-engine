from __future__ import annotations

import datetime

import pytest

from mint.directdebit import CollectionState, Mandate, MandateStatus
from mint.errors import Refused
from mint.money import Money

SIGNED = datetime.date(2026, 1, 1)
SOON = datetime.date(2026, 1, 15)
MUCH_LATER = datetime.date(2028, 1, 1)


def _mandate() -> Mandate:
    return Mandate(reference="M-1", payer="alice", signed_on=SIGNED)


class TestStatus:
    def test_a_fresh_mandate_is_active(self):
        assert _mandate().status(SOON) is MandateStatus.ACTIVE

    def test_it_goes_dormant_after_long_disuse(self):
        assert _mandate().status(MUCH_LATER) is MandateStatus.DORMANT

    def test_cancelling_is_terminal(self):
        mandate = _mandate()
        mandate.cancel(SOON)
        assert mandate.status(SOON) is MandateStatus.CANCELLED

    def test_cancelling_twice_is_refused(self):
        mandate = _mandate()
        mandate.cancel(SOON)
        with pytest.raises(Refused):
            mandate.cancel(SOON)


class TestPreNotification:
    def test_a_first_collection_needs_notice(self):
        mandate = _mandate()
        with pytest.raises(Refused) as caught:
            mandate.present("c1", Money.of(50, "USD"), SOON)
        assert "pre-notified" in str(caught.value)

    def test_notice_lets_the_first_collection_through(self):
        mandate = _mandate()
        mandate.notify("c1")
        collection = mandate.present("c1", Money.of(50, "USD"), SOON)
        assert collection.state is CollectionState.PRESENTED

    def test_later_collections_need_no_notice(self):
        mandate = _mandate()
        mandate.notify("c1")
        mandate.present("c1", Money.of(50, "USD"), SOON)
        second = mandate.present("c2", Money.of(50, "USD"), SOON)
        assert second.id == "c2"


class TestGuards:
    def test_a_cancelled_mandate_cannot_be_collected(self):
        mandate = _mandate()
        mandate.notify("c1")
        mandate.cancel(SOON)
        with pytest.raises(Refused) as caught:
            mandate.present("c1", Money.of(50, "USD"), SOON)
        assert "unauthorized withdrawal" in str(caught.value)

    def test_a_dormant_mandate_must_be_reconfirmed(self):
        mandate = _mandate()
        mandate.notify("c1")
        with pytest.raises(Refused) as caught:
            mandate.present("c1", Money.of(50, "USD"), MUCH_LATER)
        assert "reconfirmed" in str(caught.value)

    def test_a_nonpositive_collection_is_refused(self):
        mandate = _mandate()
        mandate.notify("c1")
        with pytest.raises(Refused):
            mandate.present("c1", Money.zero("USD"), SOON)


class TestReturns:
    def _collected(self) -> Mandate:
        mandate = _mandate()
        mandate.notify("c1")
        mandate.present("c1", Money.of(100, "USD"), SOON)
        mandate.present("c2", Money.of(60, "USD"), SOON)
        return mandate

    def test_settling_counts_toward_the_settled_total(self):
        mandate = self._collected()
        mandate.settle("c1")
        assert mandate.settled_total("USD") == Money.of(100, "USD")

    def test_a_return_leaves_the_settled_total_alone(self):
        mandate = self._collected()
        mandate.settle("c1")
        mandate.mark_returned("c2", "insufficient funds")
        assert mandate.settled_total("USD") == Money.of(100, "USD")
        assert mandate.returned_total("USD") == Money.of(60, "USD")

    def test_presented_excludes_returns(self):
        mandate = self._collected()
        mandate.mark_returned("c2", "account closed")
        assert mandate.presented_total("USD") == Money.of(100, "USD")

    def test_a_return_needs_a_reason(self):
        mandate = self._collected()
        with pytest.raises(Refused):
            mandate.mark_returned("c1", "   ")

    def test_returning_twice_is_refused(self):
        mandate = self._collected()
        mandate.mark_returned("c1", "insufficient funds")
        with pytest.raises(Refused):
            mandate.mark_returned("c1", "again")

    def test_an_unknown_collection_is_refused(self):
        with pytest.raises(Refused):
            self._collected().settle("nope")
