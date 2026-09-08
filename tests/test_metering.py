from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.metering import Aggregation, Meter, UsageEvent

START = datetime.datetime(2026, 3, 1, 0, 0)
END = datetime.datetime(2026, 3, 31, 23, 59)


def _events(meter: Meter) -> Meter:
    meter.record(UsageEvent(datetime.datetime(2026, 3, 2, 9, 0), 10, "alice"))
    meter.record(UsageEvent(datetime.datetime(2026, 3, 10, 9, 0), 30, "bob"))
    meter.record(UsageEvent(datetime.datetime(2026, 3, 20, 9, 0), 20, "alice"))
    meter.record(UsageEvent(datetime.datetime(2026, 4, 2, 9, 0), 99, "carol"))
    return meter


class TestAggregations:
    def test_sum_accumulates(self):
        meter = _events(Meter("bytes", Aggregation.SUM))
        assert meter.quantity_for(START, END) == 60

    def test_peak_takes_the_largest(self):
        meter = _events(Meter("capacity", Aggregation.PEAK))
        assert meter.quantity_for(START, END) == 30

    def test_unique_counts_subjects_once(self):
        meter = _events(Meter("seats", Aggregation.UNIQUE))
        assert meter.quantity_for(START, END) == 2

    def test_last_takes_the_final_value(self):
        meter = _events(Meter("plan", Aggregation.LAST))
        assert meter.quantity_for(START, END) == 20

    def test_the_rules_genuinely_differ(self):
        totals = {
            rule: _events(Meter("m", rule)).quantity_for(START, END)
            for rule in (Aggregation.SUM, Aggregation.PEAK, Aggregation.UNIQUE)
        }
        assert len(set(totals.values())) == 3


class TestPeriod:
    def test_events_outside_the_period_are_excluded(self):
        meter = _events(Meter("bytes", Aggregation.SUM))
        assert meter.event_count(START, END) == 3

    def test_an_empty_period_meters_zero(self):
        meter = _events(Meter("bytes", Aggregation.SUM))
        empty_start = datetime.datetime(2026, 5, 1)
        empty_end = datetime.datetime(2026, 5, 31)
        assert meter.quantity_for(empty_start, empty_end) == 0

    def test_a_backward_period_is_refused(self):
        meter = Meter("bytes", Aggregation.SUM)
        with pytest.raises(Refused):
            meter.quantity_for(END, START)


class TestEvents:
    def test_a_negative_quantity_is_refused(self):
        with pytest.raises(Refused):
            UsageEvent(START, -1)

    def test_late_arrivals_are_reported_separately(self):
        meter = Meter("bytes", Aggregation.SUM)
        closed = datetime.datetime(2026, 4, 5, 12, 0)
        meter.record(UsageEvent(datetime.datetime(2026, 3, 5), 5))
        meter.record(
            UsageEvent(
                datetime.datetime(2026, 3, 20),
                7,
                recorded_at=datetime.datetime(2026, 4, 10),
            )
        )
        late = meter.late_arrivals(START, END, closed)
        assert [event.quantity for event in late] == [7]

    def test_an_event_known_before_the_close_is_not_late(self):
        meter = Meter("bytes", Aggregation.SUM)
        meter.record(UsageEvent(datetime.datetime(2026, 3, 5), 5))
        closed = datetime.datetime(2026, 4, 5, 12, 0)
        assert meter.late_arrivals(START, END, closed) == []
