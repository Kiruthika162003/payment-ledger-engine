from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.relatedparty import (
    RelatedParty,
    RelatedPartyRegister,
    RelatedTransaction,
    Relationship,
)

DAY = datetime.date(2026, 6, 1)


def _register() -> RelatedPartyRegister:
    register = RelatedPartyRegister("USD")
    register.register(RelatedParty("D1", "Jane Director", Relationship.DIRECTOR))
    register.register(RelatedParty("S1", "Subsidiary Ltd", Relationship.SUBSIDIARY))
    register.record(
        RelatedTransaction("D1", DAY, Money.of(500, "USD"), "consulting fee")
    )
    register.record(
        RelatedTransaction(
            "S1", DAY, Money.of(200000, "USD"), "goods sold",
            outstanding=Money.of(50000, "USD"),
        )
    )
    return register


class TestRelationship:
    def test_a_registered_party_is_related(self):
        assert _register().is_related("D1")

    def test_a_stranger_is_not(self):
        assert not _register().is_related("X9")

    def test_a_transaction_with_a_stranger_is_refused(self):
        register = _register()
        with pytest.raises(Refused) as caught:
            register.record(
                RelatedTransaction("X9", DAY, Money.of(999999, "USD"), "huge sale")
            )
        assert "however large it is" in str(caught.value)

    def test_a_tiny_transaction_with_a_director_still_counts(self):
        register = _register()
        register.record(RelatedTransaction("D1", DAY, Money.of(1, "USD"), "lunch"))
        assert register.total_with("D1") == Money.of(501, "USD")

    def test_parties_group_by_relationship(self):
        assert len(_register().by_relationship(Relationship.DIRECTOR)) == 1


class TestTotals:
    def test_the_total_with_a_party(self):
        assert _register().total_with("S1") == Money.of(200000, "USD")

    def test_outstanding_is_tracked_separately(self):
        register = _register()
        assert register.outstanding_with("S1") == Money.of(50000, "USD")
        assert register.outstanding_with("D1").is_zero()

    def test_the_grand_total(self):
        assert _register().total_all() == Money.of(200500, "USD")

    def test_the_share_of_revenue(self):
        share = _register().share_of_revenue("S1", Money.of(1000000, "USD"))
        assert share == Fraction(1, 5)

    def test_no_share_without_revenue(self):
        assert _register().share_of_revenue("S1", Money.zero("USD")) is None


class TestDisclosure:
    def test_material_parties_are_named(self):
        material = _register().material_parties(Money.of(1000, "USD"))
        assert material == ["S1"]

    def test_a_low_threshold_names_everyone(self):
        material = _register().material_parties(Money.of(1, "USD"))
        assert material == ["D1", "S1"]

    def test_the_disclosure_lines_carry_both_figures(self):
        lines = _register().disclosure_lines(Money.of(1000, "USD"))
        assert "Subsidiary Ltd" in lines[0]
        assert "outstanding" in lines[0]

    def test_the_relationship_appears_in_the_note(self):
        lines = _register().disclosure_lines(Money.of(1, "USD"))
        assert any("director" in line for line in lines)


class TestRefusals:
    def test_a_duplicate_party_is_refused(self):
        register = _register()
        with pytest.raises(Refused):
            register.register(RelatedParty("D1", "Again", Relationship.DIRECTOR))

    def test_a_nameless_party_is_refused(self):
        with pytest.raises(Refused):
            RelatedParty("X", "  ", Relationship.DIRECTOR)

    def test_a_nonpositive_transaction_is_refused(self):
        with pytest.raises(Refused):
            RelatedTransaction("D1", DAY, Money.zero("USD"), "nothing")

    def test_more_outstanding_than_transacted_is_refused(self):
        with pytest.raises(Refused):
            RelatedTransaction(
                "D1", DAY, Money.of(100, "USD"), "odd",
                outstanding=Money.of(500, "USD"),
            )

    def test_a_wrong_currency_transaction_is_refused(self):
        register = _register()
        with pytest.raises(Refused):
            register.record(
                RelatedTransaction("D1", DAY, Money.of(100, "EUR"), "euro fee")
            )
