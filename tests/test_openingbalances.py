from __future__ import annotations

import datetime

import pytest

from mint.accounts import AccountType
from mint.chart import Chart
from mint.errors import Refused
from mint.ledger import Ledger
from mint.money import Money
from mint.openingbalances import OpeningBalanceSet

DAY = datetime.date(2026, 1, 1)


def _ledger() -> Ledger:
    chart = Chart()
    chart.add("1000", "Cash", AccountType.ASSET, "USD")
    chart.add("1200", "Receivable", AccountType.ASSET, "USD")
    chart.add("2000", "Payable", AccountType.LIABILITY, "USD")
    chart.add("3000", "Capital", AccountType.EQUITY, "USD")
    chart.add("3999", "Migration Suspense", AccountType.EQUITY, "USD")
    chart.add("1500", "Cash EUR", AccountType.ASSET, "EUR")
    return Ledger(chart)


def _balanced() -> OpeningBalanceSet:
    opening = OpeningBalanceSet("USD", DAY)
    opening.add("1000", Money.of(50000, "USD"))
    opening.add("1200", Money.of(20000, "USD"))
    opening.add("2000", Money.of("-30000.00", "USD"))
    opening.add("3000", Money.of("-40000.00", "USD"))
    return opening


class TestValidation:
    def test_a_balanced_set_is_importable(self):
        assert _balanced().balances()
        assert _balanced().is_importable(_ledger())

    def test_an_unbalanced_set_is_reported(self):
        opening = _balanced()
        opening.add("3999", Money.of(500, "USD"))
        problems = opening.validate(_ledger())
        assert any(problem.account == "(all)" for problem in problems)

    def test_an_unbalanced_set_names_the_gap(self):
        opening = OpeningBalanceSet("USD", DAY)
        opening.add("1000", Money.of(100, "USD"))
        problems = opening.validate(_ledger())
        assert any("already wrong about this" in p.reason for p in problems)

    def test_a_missing_account_is_reported(self):
        opening = _balanced()
        opening.add("9999", Money.zero("USD"))
        problems = opening.validate(_ledger())
        assert any(problem.account == "9999" for problem in problems)

    def test_every_problem_is_reported_at_once(self):
        opening = OpeningBalanceSet("USD", DAY)
        opening.add("9998", Money.of(10, "USD"))
        opening.add("9999", Money.of(20, "USD"))
        assert len(opening.validate(_ledger())) == 3

    def test_a_wrong_currency_account_is_reported(self):
        opening = _balanced()
        opening.add("1500", Money.zero("USD"))
        problems = opening.validate(_ledger())
        assert any(problem.account == "1500" for problem in problems)


class TestPosting:
    def test_a_balanced_set_posts_as_one_entry(self):
        ledger = _ledger()
        entry = _balanced().post_into(ledger, "3999")
        assert ledger.entry_count() == 1
        assert entry.ref == "MIGRATION"
        assert entry.is_balanced()

    def test_the_balances_land_correctly(self):
        ledger = _ledger()
        _balanced().post_into(ledger, "3999")
        assert ledger.balance("1000") == Money.of(50000, "USD")
        assert ledger.balance("2000") == Money.of(30000, "USD")

    def test_an_unbalanced_set_uses_the_suspense_leg(self):
        ledger = _ledger()
        opening = OpeningBalanceSet("USD", DAY)
        opening.add("1000", Money.of(100, "USD"))
        opening.post_into(ledger, "3999")
        assert ledger.balance("3999") == Money.of(100, "USD")
        assert ledger.is_balanced()

    def test_a_missing_account_blocks_the_post(self):
        ledger = _ledger()
        opening = _balanced()
        opening.add("9999", Money.zero("USD"))
        with pytest.raises(Refused) as caught:
            opening.post_into(ledger, "3999")
        assert "9999" in str(caught.value)

    def test_an_empty_set_is_refused(self):
        with pytest.raises(Refused):
            OpeningBalanceSet("USD", DAY).build_entry("3999")

    def test_an_all_zero_set_is_refused(self):
        opening = OpeningBalanceSet("USD", DAY)
        opening.add("1000", Money.zero("USD"))
        with pytest.raises(Refused):
            opening.build_entry("3999")

    def test_a_duplicate_account_is_refused(self):
        opening = _balanced()
        with pytest.raises(Refused):
            opening.add("1000", Money.of(1, "USD"))

    def test_a_wrong_currency_line_is_refused(self):
        with pytest.raises(Refused):
            OpeningBalanceSet("USD", DAY).add("1500", Money.of(1, "EUR"))
