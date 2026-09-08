from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.posting import credit, debit
from mint.recurring import RecurringTemplate

ANCHOR = datetime.date(2026, 1, 31)
MARCH_END = datetime.date(2026, 3, 31)


def _template(**kwargs) -> RecurringTemplate:
    return RecurringTemplate(
        name="rent",
        postings=(
            debit("5000", Money.of(1000, "USD")),
            credit("1000", Money.of(1000, "USD")),
        ),
        anchor=ANCHOR,
        **kwargs,
    )


class TestSchedule:
    def test_month_ends_clamp_and_return(self):
        template = _template()
        assert template.scheduled_dates(MARCH_END) == [
            datetime.date(2026, 1, 31),
            datetime.date(2026, 2, 28),
            datetime.date(2026, 3, 31),
        ]

    def test_an_occurrence_cap_stops_it(self):
        template = _template(occurrences=2)
        assert len(template.scheduled_dates(MARCH_END)) == 2

    def test_an_end_date_stops_it(self):
        template = _template(until=datetime.date(2026, 2, 28))
        assert len(template.scheduled_dates(MARCH_END)) == 2


class TestGeneration:
    def test_generating_produces_one_entry_per_due_date(self):
        template = _template()
        entries = template.generate(MARCH_END)
        assert len(entries) == 3
        assert all(item.is_balanced() for item in entries)

    def test_generating_twice_does_not_double_post(self):
        template = _template()
        template.generate(MARCH_END)
        assert template.generate(MARCH_END) == []

    def test_a_later_run_picks_up_only_the_new_ones(self):
        template = _template()
        template.generate(datetime.date(2026, 2, 28))
        fresh = template.generate(MARCH_END)
        assert [item.date for item in fresh] == [datetime.date(2026, 3, 31)]

    def test_entries_carry_the_template_name_and_tag(self):
        template = _template()
        first = template.generate(ANCHOR)[0]
        assert first.ref == "rent"
        assert "recurring" in first.tags


class TestFinish:
    def test_a_capped_template_finishes(self):
        template = _template(occurrences=2)
        template.generate(MARCH_END)
        assert template.is_finished(MARCH_END)

    def test_an_open_ended_template_never_finishes(self):
        template = _template()
        template.generate(MARCH_END)
        assert not template.is_finished(MARCH_END)


class TestRefusals:
    def test_a_template_with_no_postings_is_refused(self):
        with pytest.raises(Refused):
            RecurringTemplate(name="x", postings=(), anchor=ANCHOR)

    def test_zero_occurrences_is_refused(self):
        with pytest.raises(Refused):
            _template(occurrences=0)
