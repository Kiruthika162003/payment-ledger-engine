from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.chart import Chart
from mint.errors import Refused
from mint.journal import Journal, JournalSet, standard_journals
from mint.ledger import Ledger
from mint.money import Money
from mint.posting import credit, debit
from mint.sequence import GaplessSequence

DAY = datetime.date(2026, 4, 1)


def _ledger() -> Ledger:
    chart = Chart()
    chart.add("1000", "Cash", AccountType.ASSET, "USD")
    chart.add("4000", "Sales", AccountType.INCOME, "USD")
    chart.add("5000", "Wages", AccountType.EXPENSE, "USD")
    return Ledger(chart)


def _sale():
    return [debit("1000", Money.of(100, "USD")), credit("4000", Money.of(100, "USD"))]


class TestNumbering:
    def test_each_journal_numbers_its_own_entries(self):
        journals = standard_journals(_ledger())
        first = journals.post("SJ", _sale(), DAY)
        second = journals.post("CR", _sale(), DAY)
        assert first.ref == "SJ-00001"
        assert second.ref == "CR-00001"

    def test_numbering_is_gapless_within_a_journal(self):
        journals = standard_journals(_ledger())
        refs = [journals.post("SJ", _sale(), DAY).ref for _ in range(3)]
        assert refs == ["SJ-00001", "SJ-00002", "SJ-00003"]

    def test_the_next_reference_can_be_previewed(self):
        journals = standard_journals(_ledger())
        assert journals.get("SJ").next_reference() == "SJ-00001"
        journals.post("SJ", _sale(), DAY)
        assert journals.get("SJ").next_reference() == "SJ-00002"


class TestFiling:
    def test_entries_can_be_read_back_by_journal(self):
        journals = standard_journals(_ledger())
        journals.post("SJ", _sale(), DAY)
        journals.post("SJ", _sale(), DAY)
        journals.post("CR", _sale(), DAY)
        assert len(journals.entries_of("SJ")) == 2
        assert len(journals.entries_of("CR")) == 1

    def test_the_reference_index_maps_back_to_journals(self):
        journals = standard_journals(_ledger())
        journals.post("SJ", _sale(), DAY)
        assert journals.reference_index()["SJ-00001"] == "SJ"

    def test_all_journals_share_one_ledger(self):
        ledger = _ledger()
        journals = JournalSet(ledger)
        journals.register(Journal("SJ", "sales", GaplessSequence(prefix="SJ-")))
        journals.register(Journal("CR", "receipts", GaplessSequence(prefix="CR-")))
        journals.post("SJ", _sale(), DAY)
        journals.post("CR", _sale(), DAY)
        assert ledger.entry_count() == 2
        assert ledger.is_balanced()

    def test_the_total_counts_across_journals(self):
        journals = standard_journals(_ledger())
        journals.post("SJ", _sale(), DAY)
        journals.post("CR", _sale(), DAY)
        assert journals.total_entries() == 2


class TestRestrictions:
    def test_a_restricted_journal_refuses_a_stray_account(self):
        ledger = _ledger()
        journals = JournalSet(ledger)
        journals.register(
            Journal(
                "SJ",
                "sales journal",
                GaplessSequence(prefix="SJ-"),
                allowed_accounts=frozenset({"1000", "4000"}),
            )
        )
        postings = [
            debit("5000", Money.of(10, "USD")),
            credit("1000", Money.of(10, "USD")),
        ]
        with pytest.raises(Refused) as caught:
            journals.post("SJ", postings, DAY)
        assert "far cheaper" in str(caught.value)

    def test_an_allowed_account_passes(self):
        ledger = _ledger()
        journals = JournalSet(ledger)
        journals.register(
            Journal(
                "SJ",
                "sales journal",
                GaplessSequence(prefix="SJ-"),
                allowed_accounts=frozenset({"1000", "4000"}),
            )
        )
        assert journals.post("SJ", _sale(), DAY).ref == "SJ-00001"


class TestRefusals:
    def test_a_duplicate_journal_code_is_refused(self):
        journals = standard_journals(_ledger())
        with pytest.raises(Refused):
            journals.register(Journal("SJ", "again", GaplessSequence()))

    def test_an_unknown_journal_is_refused(self):
        with pytest.raises(Refused):
            standard_journals(_ledger()).get("ZZ")
