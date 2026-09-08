from __future__ import annotations

import pytest

from mint.dunning import DunningLadder, DunningStep, standard_ladder
from mint.errors import Refused


class TestLadder:
    def test_nothing_is_due_before_the_first_threshold(self):
        ladder = standard_ladder()
        assert ladder.next_step(0) is None

    def test_the_first_rung_comes_due(self):
        ladder = standard_ladder()
        assert ladder.next_step(1).name == "reminder"

    def test_a_sent_step_is_not_repeated(self):
        ladder = standard_ladder()
        ladder.send(20)
        assert ladder.next_step(20).name == "second notice"
        ladder.send(20)
        assert ladder.next_step(20) is None

    def test_a_long_overdue_invoice_advances_one_rung_at_a_time(self):
        ladder = standard_ladder()
        first = ladder.send(200)
        second = ladder.send(200)
        assert first.name == "reminder"
        assert second.name == "second notice"


class TestExhaustion:
    def test_the_ladder_runs_out(self):
        ladder = standard_ladder()
        for _ in range(4):
            ladder.send(500)
        assert ladder.is_exhausted()
        assert ladder.send(500) is None

    def test_remaining_reports_what_is_left(self):
        ladder = standard_ladder()
        ladder.send(100)
        assert len(ladder.remaining()) == 3


class TestConstruction:
    def test_an_empty_ladder_is_refused(self):
        with pytest.raises(Refused):
            DunningLadder(steps=())

    def test_out_of_order_thresholds_are_refused(self):
        with pytest.raises(Refused) as caught:
            DunningLadder(
                steps=(
                    DunningStep("late", 30, "x"),
                    DunningStep("early", 10, "y"),
                )
            )
        assert "out of order" in str(caught.value)

    def test_a_negative_threshold_is_refused(self):
        with pytest.raises(Refused):
            DunningLadder(steps=(DunningStep("a", -1, "x"),))
