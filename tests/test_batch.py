from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.batch import Batch
from mint.chart import Chart
from mint.entry import entry
from mint.errors import Refused
from mint.ledger import Ledger
from mint.money import Money
from mint.posting import credit, debit

DAY = datetime.date(2026, 4, 1)
AT = datetime.datetime(2026, 4, 1, 10, 0)


def _ledger() -> Ledger:
    chart = Chart()
    chart.add("1000", "Cash", AccountType.ASSET, "USD")
    chart.add("4000", "Sales", AccountType.INCOME, "USD")
    chart.add("1500", "Cash EUR", AccountType.ASSET, "EUR")
    return Ledger(chart)


def _good():
    return entry(
        [debit("1000", Money.of(100, "USD")), credit("4000", Money.of(100, "USD"))],
        DAY,
    )


def _unknown_account():
    return entry(
        [debit("9999", Money.of(100, "USD")), credit("4000", Money.of(100, "USD"))],
        DAY,
    )


class TestCleanBatch:
    def test_a_clean_batch_posts_everything(self):
        ledger = _ledger()
        batch = Batch("B-1")
        for _ in range(3):
            batch.add(_good())
        result = batch.commit(ledger, AT)
        assert result.succeeded()
        assert result.posted == 3
        assert ledger.entry_count() == 3

    def test_a_dry_run_posts_nothing(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_good())
        result = batch.dry_run(ledger)
        assert result.posted == 1
        assert ledger.entry_count() == 0
        assert result.committed_at is None

    def test_the_commit_records_when(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_good())
        assert batch.commit(ledger, AT).committed_at == AT


class TestAllOrNothing:
    def test_one_bad_entry_stops_the_whole_batch(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_good())
        batch.add(_unknown_account())
        batch.add(_good())
        result = batch.commit(ledger, AT)
        assert not result.succeeded()
        assert result.posted == 0
        assert ledger.entry_count() == 0

    def test_every_problem_is_reported_not_just_the_first(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_unknown_account())
        batch.add(_unknown_account())
        result = batch.commit(ledger, AT)
        assert len(result.problems) == 2

    def test_problems_name_their_position(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_good())
        batch.add(_unknown_account())
        result = batch.commit(ledger, AT)
        assert result.first_problem().position == 1

    def test_a_currency_mismatch_is_caught(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(
            entry(
                [
                    debit("1500", Money.of(10, "USD")),
                    credit("4000", Money.of(10, "USD")),
                ],
                DAY,
            )
        )
        result = batch.commit(ledger, AT)
        assert "holds EUR" in result.first_problem().reason

    def test_a_failed_batch_can_be_retried_after_fixing(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_unknown_account())
        batch.commit(ledger, AT)
        fixed = Batch("B-2")
        fixed.add(_good())
        assert fixed.commit(ledger, AT).succeeded()


class TestRefusals:
    def test_an_empty_batch_is_refused(self):
        with pytest.raises(Refused):
            Batch("B-1").commit(_ledger(), AT)

    def test_committing_twice_is_refused(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_good())
        batch.commit(ledger, AT)
        with pytest.raises(Refused):
            batch.commit(ledger, AT)

    def test_adding_after_commit_is_refused(self):
        ledger = _ledger()
        batch = Batch("B-1")
        batch.add(_good())
        batch.commit(ledger, AT)
        with pytest.raises(Refused):
            batch.add(_good())
