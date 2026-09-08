from __future__ import annotations

import datetime

from mint.accounts import AccountType
from mint.book import Book
from mint.integrity import Severity, errors, is_clean, run_all
from mint.money import Money
from mint.period import PeriodCalendar

DAY = datetime.date(2026, 1, 15)


def _book() -> Book:
    book = Book()
    book.open("1000", "Cash", AccountType.ASSET, "USD")
    book.open("4000", "Sales", AccountType.INCOME, "USD")
    book.post(
        book.transaction(DAY).debit("1000", Money.of(100, "USD")).credit(
            "4000", Money.of(100, "USD")
        )
    )
    return book


class TestCleanLedger:
    def test_a_healthy_ledger_has_no_errors(self):
        assert is_clean(run_all(_book().ledger))

    def test_an_unused_account_is_only_a_warning(self):
        book = _book()
        book.open("9000", "Unused", AccountType.EXPENSE, "USD")
        findings = run_all(book.ledger)
        assert is_clean(findings)
        assert any(
            f.check == "unused_accounts" and f.severity is Severity.WARNING
            for f in findings
        )


class TestDamage:
    def test_an_account_removed_from_the_chart_is_caught(self):
        book = _book()
        del book.chart.accounts["1000"]
        findings = run_all(book.ledger)
        assert not is_clean(findings)
        assert any(f.check == "accounts_exist" for f in errors(findings))

    def test_a_currency_drift_is_caught(self):
        book = _book()
        account = book.chart.accounts["1000"]
        book.chart.accounts["1000"] = type(account)(
            account.code, account.name, account.type, "EUR", account.parent
        )
        findings = run_all(book.ledger)
        assert any(f.check == "currency_consistency" for f in errors(findings))

    def test_a_parent_loop_is_caught(self):
        book = _book()
        account = book.chart.accounts["1000"]
        book.chart.accounts["1000"] = type(account)(
            account.code, account.name, account.type, account.currency, "1000"
        )
        findings = run_all(book.ledger)
        assert any(f.check == "chart_acyclic" for f in errors(findings))

    def test_all_findings_are_returned_not_just_the_first(self):
        book = _book()
        book.open("9000", "Unused", AccountType.EXPENSE, "USD")
        del book.chart.accounts["1000"]
        findings = run_all(book.ledger)
        assert len({f.check for f in findings}) >= 2


class TestPeriods:
    def test_an_entry_outside_every_period_is_caught(self):
        calendar = PeriodCalendar()
        calendar.add_months_from(datetime.date(2027, 1, 1), 1)
        findings = run_all(_book().ledger, calendar)
        assert any(f.check == "periods_cover" for f in errors(findings))

    def test_a_covered_entry_passes(self):
        calendar = PeriodCalendar()
        calendar.add_months_from(datetime.date(2026, 1, 1), 3)
        findings = run_all(_book().ledger, calendar)
        assert not any(f.check == "periods_cover" for f in findings)
