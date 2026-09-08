from __future__ import annotations

from fractions import Fraction

import pytest

from mint.consolidation import EntityFigures, consolidate, ownership_weighted
from mint.entity import Entity, Group
from mint.errors import Refused
from mint.money import Money


def _group() -> Group:
    group = Group()
    group.add(Entity("P", "Parent", "USD"))
    group.add(Entity("S", "Sub", "USD"))
    group.add(Entity("A", "Associate", "USD"))
    group.own("P", "S", Fraction(60, 100))
    group.own("P", "A", Fraction(30, 100))
    return group


def _figures() -> dict[str, EntityFigures]:
    return {
        "P": EntityFigures(
            "P", Money.of(1000, "USD"), Money.of(400, "USD"), Money.of(600, "USD"),
            Money.of(900, "USD"),
        ),
        "S": EntityFigures(
            "S", Money.of(500, "USD"), Money.of(200, "USD"), Money.of(300, "USD"),
            Money.of(400, "USD"),
        ),
        "A": EntityFigures(
            "A", Money.of(200, "USD"), Money.of(50, "USD"), Money.of(150, "USD"),
            Money.of(100, "USD"),
        ),
    }


class TestCombination:
    def test_controlled_entities_combine_at_full_value(self):
        result = consolidate(_group(), "P", _figures(), "USD")
        assert result.combined_assets == Money.of(1500, "USD")
        assert result.included == ("P", "S")

    def test_an_associate_is_excluded_from_combination(self):
        result = consolidate(_group(), "P", _figures(), "USD")
        assert result.excluded == ("A",)

    def test_revenue_combines_too(self):
        result = consolidate(_group(), "P", _figures(), "USD")
        assert result.combined_revenue == Money.of(1300, "USD")


class TestMinority:
    def test_the_outside_share_of_subsidiary_equity_is_recognized(self):
        result = consolidate(_group(), "P", _figures(), "USD")
        # 40% of the subsidiary's 300 equity belongs to outsiders.
        assert result.minority_interest == Money.of(120, "USD")

    def test_parent_equity_is_the_rest(self):
        result = consolidate(_group(), "P", _figures(), "USD")
        assert result.parent_equity() == Money.of(780, "USD")

    def test_a_wholly_owned_subsidiary_has_no_minority(self):
        group = Group()
        group.add(Entity("P", "Parent", "USD"))
        group.add(Entity("S", "Sub", "USD"))
        group.own("P", "S", Fraction(1))
        result = consolidate(group, "P", _figures(), "USD")
        assert result.minority_interest.is_zero()


class TestElimination:
    def test_intercompany_is_removed_from_both_sides(self):
        result = consolidate(
            _group(), "P", _figures(), "USD", intercompany=Money.of(100, "USD")
        )
        assert result.group_assets() == Money.of(1400, "USD")
        assert result.group_liabilities() == Money.of(500, "USD")

    def test_the_consolidated_sheet_balances(self):
        result = consolidate(
            _group(), "P", _figures(), "USD", intercompany=Money.of(100, "USD")
        )
        assert result.balances()


class TestRefusals:
    def test_missing_figures_are_refused(self):
        figures = _figures()
        del figures["S"]
        with pytest.raises(Refused):
            consolidate(_group(), "P", figures, "USD")

    def test_an_untranslated_entity_is_refused(self):
        figures = _figures()
        figures["S"] = EntityFigures(
            "S", Money.of(500, "EUR"), Money.of(200, "EUR"), Money.of(300, "EUR"),
            Money.of(400, "EUR"),
        )
        with pytest.raises(Refused) as caught:
            consolidate(_group(), "P", figures, "USD")
        assert "translate it" in str(caught.value)

    def test_ownership_weighting_scales_an_amount(self):
        assert ownership_weighted(Money.of(300, "USD"), Fraction(40, 100)) == Money.of(
            120, "USD"
        )
