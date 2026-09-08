from __future__ import annotations

import pytest

from mint.accounts import AccountType
from mint.chart import Chart
from mint.errors import DuplicateAccount, Refused, UnknownAccount


def _chart() -> Chart:
    chart = Chart()
    chart.add("1000", "Assets", AccountType.ASSET, "USD")
    chart.add("1100", "Cash", AccountType.ASSET, "USD", parent="1000")
    chart.add("1110", "Checking", AccountType.ASSET, "USD", parent="1100")
    chart.add("1120", "Savings", AccountType.ASSET, "USD", parent="1100")
    chart.add("2000", "Liabilities", AccountType.LIABILITY, "USD")
    return chart


class TestOpen:
    def test_a_duplicate_code_is_refused(self):
        chart = _chart()
        with pytest.raises(DuplicateAccount):
            chart.add("1000", "Again", AccountType.ASSET, "USD")

    def test_a_missing_parent_is_refused(self):
        chart = Chart()
        with pytest.raises(UnknownAccount) as caught:
            chart.add("1110", "Checking", AccountType.ASSET, "USD", parent="1100")
        assert "1100" in str(caught.value)

    def test_a_child_must_share_its_parents_type(self):
        chart = _chart()
        with pytest.raises(Refused) as caught:
            chart.add("1130", "Odd", AccountType.LIABILITY, "USD", parent="1100")
        assert "keeps its parent's type" in str(caught.value)


class TestTraversal:
    def test_children_are_direct_only(self):
        chart = _chart()
        assert [a.code for a in chart.children("1100")] == ["1110", "1120"]

    def test_descendants_reach_the_whole_subtree(self):
        chart = _chart()
        assert [a.code for a in chart.descendants("1000")] == ["1100", "1110", "1120"]

    def test_roots_have_no_parent(self):
        chart = _chart()
        assert [a.code for a in chart.roots()] == ["1000", "2000"]

    def test_of_type_filters_by_type(self):
        chart = _chart()
        assert [a.code for a in chart.of_type(AccountType.LIABILITY)] == ["2000"]


class TestLookup:
    def test_get_refuses_an_unknown_code(self):
        with pytest.raises(UnknownAccount):
            _chart().get("9999")

    def test_has_reports_membership(self):
        chart = _chart()
        assert chart.has("1000")
        assert not chart.has("9999")
