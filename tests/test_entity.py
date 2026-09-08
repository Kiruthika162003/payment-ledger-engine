from __future__ import annotations

from fractions import Fraction

import pytest

from mint.entity import Entity, Group
from mint.errors import Refused


def _group() -> Group:
    group = Group()
    group.add(Entity("P", "Parent", "USD"))
    group.add(Entity("S1", "Sub One", "USD"))
    group.add(Entity("S2", "Sub Two", "EUR"))
    group.add(Entity("A", "Associate", "USD"))
    group.own("P", "S1", Fraction(100, 100))
    group.own("P", "S2", Fraction(60, 100))
    group.own("P", "A", Fraction(30, 100))
    return group


class TestOwnership:
    def test_shares_are_recorded(self):
        assert _group().share_of("P", "S2") == Fraction(60, 100)

    def test_control_needs_more_than_half(self):
        group = _group()
        assert group.controls("P", "S2")
        assert not group.controls("P", "A")

    def test_the_minority_share_is_the_rest(self):
        assert _group().minority_share("P", "S2") == Fraction(40, 100)

    def test_children_are_listed(self):
        assert _group().children_of("P") == ["A", "S1", "S2"]

    def test_controlled_subsidiaries_exclude_associates(self):
        assert _group().controlled_subsidiaries("P") == ["S1", "S2"]


class TestStructure:
    def test_indirect_subsidiaries_are_reached(self):
        group = _group()
        group.add(Entity("G", "Grandchild", "USD"))
        group.own("S1", "G", Fraction(1))
        assert "G" in group.subsidiaries("P")

    def test_roots_are_the_unowned(self):
        assert _group().roots() == ["P"]


class TestRefusals:
    def test_self_ownership_is_refused(self):
        with pytest.raises(Refused):
            _group().own("P", "P", Fraction(1))

    def test_a_cycle_is_refused(self):
        group = _group()
        with pytest.raises(Refused) as caught:
            group.own("S1", "P", Fraction(1))
        assert "no well-defined consolidation order" in str(caught.value)

    def test_an_indirect_cycle_is_refused(self):
        group = _group()
        group.add(Entity("G", "Grandchild", "USD"))
        group.own("S1", "G", Fraction(1))
        with pytest.raises(Refused):
            group.own("G", "P", Fraction(1))

    def test_a_share_above_one_is_refused(self):
        with pytest.raises(Refused):
            _group().own("P", "S1", Fraction(3, 2))

    def test_a_duplicate_entity_is_refused(self):
        group = _group()
        with pytest.raises(Refused):
            group.add(Entity("P", "Again", "USD"))

    def test_an_unknown_entity_is_refused(self):
        with pytest.raises(Refused):
            _group().get("Z")
