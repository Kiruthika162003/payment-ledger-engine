from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.escrow import Escrow, EscrowState
from mint.money import Money

DAY = datetime.date(2026, 1, 1)


def _escrow(amount: str = "1000.00") -> Escrow:
    return Escrow(
        id="e1",
        payer="buyer",
        payee="seller",
        amount=Money.of(amount, "USD"),
        funded_on=DAY,
        agents=frozenset({"agent"}),
    )


class TestRelease:
    def test_a_full_release_closes_the_escrow(self):
        escrow = _escrow()
        escrow.release(Money.of(1000, "USD"), DAY, "agent")
        assert escrow.state() is EscrowState.RELEASED
        assert escrow.held().is_zero()

    def test_a_partial_release_leaves_it_open(self):
        escrow = _escrow()
        escrow.release(Money.of(400, "USD"), DAY, "agent")
        assert escrow.state() is EscrowState.PARTIALLY_RELEASED
        assert escrow.held() == Money.of(600, "USD")

    def test_releasing_more_than_is_held_is_refused(self):
        escrow = _escrow()
        with pytest.raises(Refused):
            escrow.release(Money.of(1500, "USD"), DAY, "agent")


class TestAuthorization:
    def test_an_unauthorized_party_cannot_release(self):
        escrow = _escrow()
        with pytest.raises(Refused) as caught:
            escrow.release(Money.of(100, "USD"), DAY, "buyer")
        assert "not authorized" in str(caught.value)

    def test_an_escrow_needs_an_agent(self):
        with pytest.raises(Refused) as caught:
            Escrow("e", "b", "s", Money.of(1, "USD"), DAY, frozenset())
        assert "it is a delay" in str(caught.value)


class TestRefund:
    def test_a_refund_returns_what_is_left(self):
        escrow = _escrow()
        escrow.release(Money.of(300, "USD"), DAY, "agent")
        assert escrow.refund(DAY, "agent") == Money.of(700, "USD")
        assert escrow.state() is EscrowState.REFUNDED

    def test_a_refunded_escrow_cannot_be_released(self):
        escrow = _escrow()
        escrow.refund(DAY, "agent")
        with pytest.raises(Refused) as caught:
            escrow.release(Money.of(10, "USD"), DAY, "agent")
        assert "closed" in str(caught.value)


class TestDispute:
    def test_either_party_may_dispute(self):
        escrow = _escrow()
        assert escrow.dispute("buyer") is EscrowState.DISPUTED

    def test_a_stranger_cannot_dispute(self):
        with pytest.raises(Refused):
            _escrow().dispute("passerby")

    def test_a_disputed_escrow_cannot_be_released(self):
        escrow = _escrow()
        escrow.dispute("seller")
        with pytest.raises(Refused) as caught:
            escrow.release(Money.of(10, "USD"), DAY, "agent")
        assert "resolve the dispute" in str(caught.value)

    def test_resolving_reopens_release(self):
        escrow = _escrow()
        escrow.dispute("seller")
        escrow.resolve("agent")
        escrow.release(Money.of(100, "USD"), DAY, "agent")
        assert escrow.held() == Money.of(900, "USD")
