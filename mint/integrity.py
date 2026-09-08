"""Integrity checks: the questions to ask a ledger before trusting a report.

Most ledger corruption is not exotic. It is a posting to an account
that was later removed from the chart, an entry dated in a period
nobody opened, a currency that drifted between an account and its
postings, or a chart whose parent links form a loop that makes a
rollup recurse forever. Each of these is cheap to detect and
expensive to discover from a wrong report, so this module runs the
checks explicitly and returns findings rather than raising on the
first one, because an operator fixing a damaged ledger wants the
whole list rather than one problem at a time. Findings carry a
severity, since some of these make a report wrong and others merely
make it ugly, and a check that treats an unused account as
equivalent to an unbalanced ledger trains people to ignore the
output. The suite is deliberately fast enough to run before every
report, on the principle that a check nobody runs is a check that
does not exist.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from mint.ledger import Ledger
from mint.period import PeriodCalendar


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    detail: str


def check_balanced(ledger: Ledger) -> list[Finding]:
    imbalance = ledger.imbalance()
    if not imbalance:
        return []
    return [
        Finding(
            "balanced",
            Severity.ERROR,
            f"the ledger is out of balance by {imbalance}",
        )
    ]


def check_accounts_exist(ledger: Ledger) -> list[Finding]:
    found: list[Finding] = []
    for index, entry in enumerate(ledger.entries):
        for posting in entry.postings:
            if not ledger.chart.has(posting.account):
                found.append(
                    Finding(
                        "accounts_exist",
                        Severity.ERROR,
                        f"entry {index} posts to {posting.account!r}, which is "
                        "no longer in the chart",
                    )
                )
    return found


def check_currency_consistency(ledger: Ledger) -> list[Finding]:
    found: list[Finding] = []
    for index, entry in enumerate(ledger.entries):
        for posting in entry.postings:
            if not ledger.chart.has(posting.account):
                continue
            account = ledger.chart.get(posting.account)
            if posting.currency != account.currency:
                found.append(
                    Finding(
                        "currency_consistency",
                        Severity.ERROR,
                        f"entry {index} posts {posting.currency} to "
                        f"{account.code!r}, which holds {account.currency}",
                    )
                )
    return found


def check_chart_acyclic(ledger: Ledger) -> list[Finding]:
    found: list[Finding] = []
    for code in ledger.chart.accounts:
        seen: set[str] = set()
        current: str | None = code
        while current is not None:
            if current in seen:
                found.append(
                    Finding(
                        "chart_acyclic",
                        Severity.ERROR,
                        f"the parent links from {code!r} form a loop",
                    )
                )
                break
            seen.add(current)
            account = ledger.chart.accounts.get(current)
            current = account.parent if account else None
    return found


def check_periods_cover(
    ledger: Ledger, calendar: PeriodCalendar
) -> list[Finding]:
    found: list[Finding] = []
    uncovered: set[datetime.date] = set()
    for entry in ledger.entries:
        try:
            calendar.period_for(entry.date)
        except Exception:
            uncovered.add(entry.date)
    for date in sorted(uncovered):
        found.append(
            Finding(
                "periods_cover",
                Severity.ERROR,
                f"no accounting period covers {date.isoformat()}",
            )
        )
    return found


def check_unused_accounts(ledger: Ledger) -> list[Finding]:
    found: list[Finding] = []
    for code in sorted(ledger.chart.accounts):
        if ledger.raw_debits(code) == 0 and ledger.raw_credits(code) == 0:
            found.append(
                Finding(
                    "unused_accounts",
                    Severity.WARNING,
                    f"account {code!r} has never been posted to",
                )
            )
    return found


def run_all(ledger: Ledger, calendar: PeriodCalendar | None = None) -> list[Finding]:
    findings = [
        *check_balanced(ledger),
        *check_accounts_exist(ledger),
        *check_currency_consistency(ledger),
        *check_chart_acyclic(ledger),
        *check_unused_accounts(ledger),
    ]
    if calendar is not None:
        findings.extend(check_periods_cover(ledger, calendar))
    return findings


def errors(findings: list[Finding]) -> list[Finding]:
    return [item for item in findings if item.severity is Severity.ERROR]


def is_clean(findings: list[Finding]) -> bool:
    return not errors(findings)
