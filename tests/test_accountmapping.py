from __future__ import annotations

from fractions import Fraction

import pytest

from mint.accountmapping import ChartMapping, Mapping
from mint.errors import Refused
from mint.money import Money


def _mapping() -> ChartMapping:
    mapping = ChartMapping("USD")
    mapping.map_one("OLD-CASH", "1000")
    mapping.map_one("OLD-PETTY", "1000")
    mapping.map_many("OLD-MIXED", [("5000", Fraction(3)), ("5100", Fraction(1))])
    return mapping


def _balances() -> dict[str, Money]:
    return {
        "OLD-CASH": Money.of(1000, "USD"),
        "OLD-PETTY": Money.of(200, "USD"),
        "OLD-MIXED": Money.of(400, "USD"),
    }


class TestCollapsing:
    def test_several_old_accounts_collapse_into_one(self):
        result = _mapping().translate(_balances())
        assert result["1000"] == Money.of(1200, "USD")

    def test_the_collapse_is_visible(self):
        collapsed = _mapping().collapsed()
        assert collapsed["1000"] == ["OLD-CASH", "OLD-PETTY"]

    def test_the_targets_are_listed(self):
        assert _mapping().targets() == ["1000", "5000", "5100"]


class TestSplitting:
    def test_a_split_distributes_by_weight(self):
        result = _mapping().translate(_balances())
        assert result["5000"] == Money.of(300, "USD")
        assert result["5100"] == Money.of(100, "USD")

    def test_a_split_conserves_the_cent(self):
        mapping = ChartMapping("USD")
        mapping.map_many("ODD", [("A", Fraction(1)), ("B", Fraction(1)), ("C", Fraction(1))])
        result = mapping.translate({"ODD": Money.of("100.00", "USD")})
        assert sum(amount.units for amount in result.values()) == 10000

    def test_a_split_mapping_is_flagged(self):
        assert _mapping().mappings["OLD-MIXED"].is_split()
        assert not _mapping().mappings["OLD-CASH"].is_split()


class TestCompleteness:
    def test_an_unmapped_account_is_named(self):
        mapping = _mapping()
        assert mapping.unmapped(["OLD-CASH", "OLD-GHOST"]) == ["OLD-GHOST"]

    def test_completeness_is_reported(self):
        mapping = _mapping()
        assert mapping.is_complete(list(_balances()))
        assert not mapping.is_complete([*_balances(), "OLD-GHOST"])

    def test_translating_an_unmapped_balance_is_refused(self):
        mapping = _mapping()
        balances = {**_balances(), "OLD-GHOST": Money.of(500, "USD")}
        with pytest.raises(Refused) as caught:
            mapping.translate(balances)
        assert "would vanish" in str(caught.value)

    def test_the_total_is_preserved(self):
        assert _mapping().preserves_total(_balances())


class TestRefusals:
    def test_a_duplicate_mapping_is_refused(self):
        mapping = _mapping()
        with pytest.raises(Refused):
            mapping.map_one("OLD-CASH", "2000")

    def test_a_mapping_with_no_target_is_refused(self):
        with pytest.raises(Refused):
            Mapping("OLD", ())

    def test_a_nonpositive_weight_is_refused(self):
        with pytest.raises(Refused):
            Mapping("OLD", (("A", Fraction(0)),))

    def test_a_wrong_currency_balance_is_refused(self):
        mapping = _mapping()
        with pytest.raises(Refused):
            mapping.translate({"OLD-CASH": Money.of(1, "EUR")})
