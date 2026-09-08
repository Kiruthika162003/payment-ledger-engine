from __future__ import annotations

from fractions import Fraction

import pytest

from mint.cohort import CohortTable
from mint.errors import Refused


def _table() -> CohortTable:
    table = CohortTable()
    for customer in ("a", "b", "c", "d"):
        table.enroll("2026-01", customer)
    for customer in ("e", "f"):
        table.enroll("2026-02", customer)
    for customer in ("a", "b", "c", "d"):
        table.record_activity("2026-01", 0, customer)
    for customer in ("a", "b"):
        table.record_activity("2026-01", 1, customer)
    table.record_activity("2026-01", 2, "a")
    for customer in ("e", "f"):
        table.record_activity("2026-02", 0, customer)
        table.record_activity("2026-02", 1, customer)
    return table


class TestRetention:
    def test_period_zero_is_the_whole_cohort(self):
        assert _table().retention("2026-01", 0) == Fraction(1)

    def test_retention_falls_over_time(self):
        table = _table()
        assert table.retention("2026-01", 1) == Fraction(1, 2)
        assert table.retention("2026-01", 2) == Fraction(1, 4)

    def test_it_measures_against_the_starting_size(self):
        table = _table()
        # Period two is one of four, not one of the two active in period one.
        assert table.retention("2026-01", 2) == Fraction(1, 4)

    def test_a_returning_customer_counts_as_active(self):
        table = _table()
        table.record_activity("2026-01", 3, "c")
        assert table.retention("2026-01", 3) == Fraction(1, 4)


class TestTable:
    def test_a_row_covers_the_requested_periods(self):
        assert len(_table().row("2026-01", 3)) == 3

    def test_the_table_lists_every_cohort(self):
        assert sorted(_table().table(2)) == ["2026-01", "2026-02"]

    def test_cohorts_are_named(self):
        assert _table().cohort_names() == ["2026-01", "2026-02"]

    def test_a_later_cohort_can_be_compared(self):
        table = _table()
        assert table.improving("2026-01", "2026-02", 1) is True


class TestRefusals:
    def test_a_customer_joins_one_cohort(self):
        table = _table()
        with pytest.raises(Refused) as caught:
            table.enroll("2026-02", "a")
        assert "double-counts" in str(caught.value)

    def test_activity_for_a_non_member_is_refused(self):
        table = _table()
        with pytest.raises(Refused):
            table.record_activity("2026-01", 0, "e")

    def test_an_unknown_cohort_is_refused(self):
        with pytest.raises(Refused):
            _table().size("2099-01")

    def test_a_negative_period_is_refused(self):
        table = _table()
        with pytest.raises(Refused):
            table.record_activity("2026-01", -1, "a")
