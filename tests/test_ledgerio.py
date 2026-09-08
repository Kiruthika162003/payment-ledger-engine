from __future__ import annotations

import datetime

import pytest

from mint.entry import entry
from mint.errors import Refused
from mint.ledgerio import export_rows, from_csv, import_rows, to_csv
from mint.money import Money
from mint.posting import credit, debit

DAY = datetime.date(2026, 5, 4)


def _entries():
    return [
        entry(
            [debit("1000", Money.of(100, "USD")), credit("4000", Money.of(100, "USD"))],
            DAY,
            memo="a sale",
            ref="INV-1",
        ),
        entry(
            [
                debit("5000", Money.of("12.34", "USD")),
                debit("5100", Money.of("0.66", "USD")),
                credit("1000", Money.of(13, "USD")),
            ],
            DAY,
            memo="split expense",
            ref="EXP-9",
        ),
    ]


class TestExport:
    def test_one_row_per_posting(self):
        assert len(export_rows(_entries())) == 5

    def test_the_csv_has_a_header(self):
        text = to_csv(_entries())
        assert text.splitlines()[0].startswith("group,date,memo")


class TestRoundTrip:
    def test_entries_survive_the_round_trip(self):
        original = _entries()
        restored = from_csv(to_csv(original))
        assert restored == original

    def test_amounts_keep_their_exact_minor_units(self):
        restored = from_csv(to_csv(_entries()))
        amounts = [p.amount.units for p in restored[1].postings]
        assert amounts == [1234, 66, 1300]

    def test_dates_memos_and_refs_survive(self):
        restored = from_csv(to_csv(_entries()))
        assert restored[0].date == DAY
        assert restored[0].memo == "a sale"
        assert restored[0].ref == "INV-1"


class TestRefusals:
    def test_an_unbalanced_group_is_refused_with_its_name(self):
        rows = [
            {
                "group": "g1", "date": DAY.isoformat(), "memo": "", "ref": "",
                "account": "1000", "side": "debit", "units": "100", "currency": "USD",
            }
        ]
        with pytest.raises(Refused) as caught:
            import_rows(rows)
        assert "g1" in str(caught.value)

    def test_a_bad_side_is_refused(self):
        rows = [
            {
                "group": "g1", "date": DAY.isoformat(), "memo": "", "ref": "",
                "account": "1000", "side": "sideways", "units": "100", "currency": "USD",
            }
        ]
        with pytest.raises(Refused) as caught:
            import_rows(rows)
        assert "debit or credit" in str(caught.value)

    def test_an_unreadable_amount_is_refused(self):
        rows = [
            {
                "group": "g1", "date": DAY.isoformat(), "memo": "", "ref": "",
                "account": "1000", "side": "debit", "units": "lots", "currency": "USD",
            }
        ]
        with pytest.raises(Refused):
            import_rows(rows)
