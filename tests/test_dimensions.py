from __future__ import annotations

import datetime

import pytest

from mint.dimensions import (
    UNALLOCATED,
    DimensionSet,
    cross_tab,
    slice_by,
    slice_total,
    unallocated_share,
)
from mint.entry import entry
from mint.errors import Refused
from mint.money import Money
from mint.posting import credit, debit

DAY = datetime.date(2026, 1, 1)


def _entries():
    return [
        entry([debit("5000", Money.of(100, "USD")), credit("1000", Money.of(100, "USD"))],
              DAY, ref="E1"),
        entry([debit("5000", Money.of(60, "USD")), credit("1000", Money.of(60, "USD"))],
              DAY, ref="E2"),
        entry([debit("5000", Money.of(40, "USD")), credit("1000", Money.of(40, "USD"))],
              DAY, ref="E3"),
    ]


def _departments() -> DimensionSet:
    dim = DimensionSet("department")
    dim.declare("sales")
    dim.declare("engineering")
    dim.tag("E1", "sales")
    dim.tag("E2", "engineering")
    return dim


class TestSlicing:
    def test_totals_split_by_dimension_value(self):
        sliced = slice_by(_entries(), _departments(), "5000", "USD")
        assert sliced["sales"] == Money.of(100, "USD")
        assert sliced["engineering"] == Money.of(60, "USD")

    def test_untagged_postings_show_as_unallocated(self):
        sliced = slice_by(_entries(), _departments(), "5000", "USD")
        assert sliced[UNALLOCATED] == Money.of(40, "USD")
        assert unallocated_share(sliced, "USD") == Money.of(40, "USD")

    def test_the_slices_add_back_to_the_account_total(self):
        sliced = slice_by(_entries(), _departments(), "5000", "USD")
        assert slice_total(sliced, "USD") == Money.of(200, "USD")


class TestCrossTab:
    def test_two_dimensions_produce_a_footing_grid(self):
        regions = DimensionSet("region")
        regions.declare("north")
        regions.tag("E1", "north")
        grid = cross_tab(_entries(), _departments(), regions, "5000", "USD")
        assert grid[("sales", "north")] == Money.of(100, "USD")
        assert grid[("engineering", UNALLOCATED)] == Money.of(60, "USD")
        total = Money.zero("USD")
        for value in grid.values():
            total = total + value
        assert total == Money.of(200, "USD")


class TestDeclaration:
    def test_tagging_an_undeclared_value_is_refused(self):
        dim = DimensionSet("department")
        with pytest.raises(Refused) as caught:
            dim.tag("E1", "ghost")
        assert "not a declared department" in str(caught.value)

    def test_a_blank_value_is_refused(self):
        with pytest.raises(Refused):
            DimensionSet("department").declare("   ")

    def test_declaring_returns_the_trimmed_value(self):
        assert DimensionSet("d").declare("  sales  ") == "sales"
