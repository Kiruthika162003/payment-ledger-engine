from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.guarantee import Guarantee, GuaranteeBook, GuaranteeState
from mint.money import Money

ISSUED = datetime.date(2026, 1, 1)
MID = datetime.date(2026, 6, 1)
EXPIRES = datetime.date(2026, 12, 31)
AFTER = datetime.date(2027, 3, 1)


def _guarantee(**kwargs) -> Guarantee:
    base = {
        "id": "G-1",
        "beneficiary": "landlord",
        "face_value": Money.of(100000, "USD"),
        "issued": ISSUED,
        "expires": EXPIRES,
    }
    base.update(kwargs)
    return Guarantee(**base)


class TestContingent:
    def test_a_live_guarantee_is_exposure_not_liability(self):
        guarantee = _guarantee()
        assert guarantee.contingent_exposure(MID) == Money.of(100000, "USD")
        assert guarantee.real_liability().is_zero()

    def test_it_is_live_until_expiry(self):
        assert _guarantee().state(MID) is GuaranteeState.LIVE

    def test_expiry_is_the_ordinary_outcome(self):
        guarantee = _guarantee()
        assert guarantee.state(AFTER) is GuaranteeState.EXPIRED
        assert guarantee.contingent_exposure(AFTER).is_zero()


class TestCalling:
    def test_a_call_creates_a_real_liability(self):
        guarantee = _guarantee()
        guarantee.call(Money.of(40000, "USD"), MID, "tenant defaulted")
        assert guarantee.real_liability() == Money.of(40000, "USD")
        assert guarantee.contingent_exposure(MID) == Money.of(60000, "USD")

    def test_a_partial_call_is_named(self):
        guarantee = _guarantee()
        guarantee.call(Money.of(40000, "USD"), MID, "partial default")
        assert guarantee.state(MID) is GuaranteeState.PARTLY_CALLED

    def test_a_full_call_exhausts_it(self):
        guarantee = _guarantee()
        guarantee.call(Money.of(100000, "USD"), MID, "full default")
        assert guarantee.state(MID) is GuaranteeState.CALLED
        assert guarantee.available().is_zero()

    def test_calling_beyond_the_face_value_is_refused(self):
        guarantee = _guarantee()
        with pytest.raises(Refused):
            guarantee.call(Money.of(200000, "USD"), MID, "too much")

    def test_calling_after_expiry_is_refused(self):
        guarantee = _guarantee()
        with pytest.raises(Refused) as caught:
            guarantee.call(Money.of(1000, "USD"), AFTER, "late")
        assert "no longer be called" in str(caught.value)

    def test_a_call_needs_a_reason(self):
        with pytest.raises(Refused):
            _guarantee().call(Money.of(1000, "USD"), MID, "  ")


class TestCommission:
    def test_commission_accrues_over_the_life(self):
        guarantee = _guarantee(commission_rate=Fraction(2, 100))
        early = guarantee.commission_to(MID)
        late = guarantee.commission_to(EXPIRES)
        assert early.is_positive()
        assert late > early

    def test_it_stops_accruing_at_expiry(self):
        guarantee = _guarantee(commission_rate=Fraction(2, 100))
        assert guarantee.commission_to(AFTER) == guarantee.commission_to(EXPIRES)

    def test_no_commission_without_a_rate(self):
        assert _guarantee().commission_to(EXPIRES).is_zero()


class TestCancellation:
    def test_an_undrawn_guarantee_can_be_cancelled(self):
        guarantee = _guarantee()
        assert guarantee.cancel(MID) is GuaranteeState.CANCELLED
        assert guarantee.contingent_exposure(MID).is_zero()

    def test_a_called_guarantee_cannot_be_cancelled(self):
        guarantee = _guarantee()
        guarantee.call(Money.of(1000, "USD"), MID, "default")
        with pytest.raises(Refused):
            guarantee.cancel(MID)

    def test_cancelling_twice_is_refused(self):
        guarantee = _guarantee()
        guarantee.cancel(MID)
        with pytest.raises(Refused):
            guarantee.cancel(MID)


class TestBook:
    def _book(self) -> GuaranteeBook:
        book = GuaranteeBook("USD")
        book.issue(_guarantee())
        book.issue(_guarantee(id="G-2", face_value=Money.of(50000, "USD")))
        return book

    def test_the_book_totals_contingent_exposure(self):
        assert self._book().total_contingent(MID) == Money.of(150000, "USD")

    def test_calls_move_into_the_liability_total(self):
        book = self._book()
        book.guarantees[0].call(Money.of(30000, "USD"), MID, "default")
        assert book.total_liability() == Money.of(30000, "USD")
        assert book.total_contingent(MID) == Money.of(120000, "USD")

    def test_live_guarantees_are_listed(self):
        book = self._book()
        assert len(book.live(MID)) == 2
        assert len(book.live(AFTER)) == 0

    def test_a_duplicate_guarantee_is_refused(self):
        book = self._book()
        with pytest.raises(Refused):
            book.issue(_guarantee())

    def test_expiry_before_issue_is_refused(self):
        with pytest.raises(Refused):
            _guarantee(expires=ISSUED)
