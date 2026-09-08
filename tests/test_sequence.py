from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.sequence import GaplessSequence


class TestIssuing:
    def test_numbers_are_formatted_with_prefix_and_width(self):
        seq = GaplessSequence(prefix="INV-", width=5)
        assert seq.issue() == "INV-00001"
        assert seq.issue() == "INV-00002"

    def test_peek_does_not_consume(self):
        seq = GaplessSequence(prefix="INV-")
        assert seq.peek() == "INV-00001"
        assert seq.peek() == "INV-00001"
        assert seq.issue() == "INV-00001"

    def test_issued_numbers_sort_in_issue_order(self):
        seq = GaplessSequence(prefix="INV-", width=4)
        numbers = [seq.issue() for _ in range(12)]
        assert numbers == sorted(numbers)


class TestReserveConfirm:
    def test_an_abandoned_number_is_returned_not_burned(self):
        seq = GaplessSequence(prefix="INV-")
        assert seq.reserve() == "INV-00001"
        seq.release()
        assert seq.issue() == "INV-00001"
        assert not seq.has_gaps()

    def test_a_confirmed_number_advances_the_counter(self):
        seq = GaplessSequence(prefix="INV-")
        seq.reserve()
        assert seq.confirm() == "INV-00001"
        assert seq.peek() == "INV-00002"

    def test_a_double_reservation_is_refused(self):
        seq = GaplessSequence()
        seq.reserve()
        with pytest.raises(Refused) as caught:
            seq.reserve()
        assert "already reserved" in str(caught.value)

    def test_confirming_nothing_is_refused(self):
        with pytest.raises(Refused):
            GaplessSequence().confirm()

    def test_releasing_nothing_is_refused(self):
        with pytest.raises(Refused):
            GaplessSequence().release()


class TestGaplessness:
    def test_a_run_of_issues_has_no_gaps(self):
        seq = GaplessSequence()
        for _ in range(20):
            seq.issue()
        assert not seq.has_gaps()
        assert seq.count() == 20

    def test_reserving_and_releasing_between_issues_keeps_it_gapless(self):
        seq = GaplessSequence()
        seq.issue()
        seq.reserve()
        seq.release()
        seq.issue()
        assert seq.issued == [1, 2]
        assert not seq.has_gaps()
