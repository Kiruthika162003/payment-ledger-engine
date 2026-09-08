from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.netting import NettingCycle


def _cycle() -> NettingCycle:
    cycle = NettingCycle("USD")
    cycle.add("A", "B", Money.of(100, "USD"))
    cycle.add("B", "C", Money.of(100, "USD"))
    cycle.add("C", "A", Money.of(100, "USD"))
    return cycle


class TestCircularDebt:
    def test_a_perfect_circle_nets_to_nothing(self):
        cycle = _cycle()
        assert cycle.netted_total().is_zero()
        assert cycle.instructions() == []

    def test_the_gross_shows_what_was_avoided(self):
        cycle = _cycle()
        assert cycle.gross_total() == Money.of(300, "USD")
        assert cycle.saving() == Money.of(300, "USD")

    def test_every_party_is_square(self):
        positions = _cycle().net_positions()
        assert all(value.is_zero() for value in positions.values())


class TestRealNetting:
    def _uneven(self) -> NettingCycle:
        cycle = NettingCycle("USD")
        cycle.add("A", "B", Money.of(500, "USD"))
        cycle.add("B", "C", Money.of(300, "USD"))
        cycle.add("C", "A", Money.of(100, "USD"))
        return cycle

    def test_positions_are_computed(self):
        positions = self._uneven().net_positions()
        assert positions["A"] == Money.of("-400.00", "USD")
        assert positions["B"] == Money.of(200, "USD")
        assert positions["C"] == Money.of(200, "USD")

    def test_netting_moves_less_than_gross(self):
        cycle = self._uneven()
        assert cycle.netted_total() < cycle.gross_total()
        assert cycle.netted_total() == Money.of(400, "USD")

    def test_positions_are_preserved_by_the_collapse(self):
        assert self._uneven().positions_preserved()

    def test_multilateral_beats_bilateral(self):
        cycle = self._uneven()
        assert cycle.netted_total() <= cycle.bilateral_total()

    def test_the_instructions_are_deterministic(self):
        first = [
            (i.payer, i.payee, i.amount.units) for i in self._uneven().instructions()
        ]
        second = [
            (i.payer, i.payee, i.amount.units) for i in self._uneven().instructions()
        ]
        assert first == second


class TestRefusals:
    def test_self_debt_is_refused(self):
        with pytest.raises(Refused):
            NettingCycle("USD").add("A", "A", Money.of(10, "USD"))

    def test_a_wrong_currency_obligation_is_refused(self):
        with pytest.raises(Refused):
            NettingCycle("USD").add("A", "B", Money.of(10, "EUR"))

    def test_a_nonpositive_obligation_is_refused(self):
        with pytest.raises(Refused):
            NettingCycle("USD").add("A", "B", Money.zero("USD"))

    def test_parties_are_listed(self):
        assert _cycle().parties() == ["A", "B", "C"]
