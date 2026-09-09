"""Assay: an amount lands in exactly one period, and the period it belongs to.

Half the errors in a ledger are timing errors: an amount that lands
in the wrong month, or in two months, or in none. This assay
measures the modules that decide when something counts. Tax points
must split a part-prepaid supply across two returns and the parts
must still sum to the whole, since a deposit in March and delivery
in April genuinely belong to different periods and a system using
one date for both reports the wrong figure twice. An accounting
period must refuse a backdated entry once it is closed, because the
promise of a close is that published figures do not move. An
accrual must reverse in the following period, since one posted and
never reversed charges the same cost twice. And a recurring
template must not generate the same month twice when the job runs
again, which is the timing error that actually happens most often
because a retry is the normal response to a failure.
"""

from __future__ import annotations

import datetime

from mint.accrual import Accrual, AccrualKind
from mint.assays.framework import Finding, assay
from mint.errors import Refused
from mint.money import Money
from mint.period import PeriodCalendar
from mint.posting import credit, debit
from mint.recurring import RecurringTemplate
from mint.taxpoint import Supply

MARCH = datetime.date(2026, 3, 15)
APRIL = datetime.date(2026, 4, 10)
DEC31 = datetime.date(2026, 12, 31)
JAN1 = datetime.date(2027, 1, 1)


@assay("periods", "does every amount land in exactly one period, and the right one")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    supply = Supply(id="S-1", total=Money.of(1000, "USD"), supplied_on=APRIL)
    supply.receive_payment(MARCH, Money.of(300, "USD"))
    findings.append(
        Finding(
            "a part-prepaid supply spans two periods",
            supply.spans_two_periods(),
            True,
        )
    )
    findings.append(
        Finding("March takes the deposit", supply.amount_in_period(2026, 3).units, 30000)
    )
    findings.append(
        Finding("April takes the balance", supply.amount_in_period(2026, 4).units, 70000)
    )
    findings.append(Finding("the parts sum to the whole", supply.points_reconcile(), True))

    calendar = PeriodCalendar()
    calendar.add_months_from(datetime.date(2026, 1, 1), 6)
    calendar.close("2026-03")
    refused = False
    try:
        calendar.guard_posting(MARCH)
    except Refused:
        refused = True
    findings.append(Finding("a closed period refuses a backdated entry", refused, True))
    findings.append(
        Finding("an open one accepts", calendar.guard_posting(APRIL).name, "2026-04")
    )

    accrual = Accrual("ac-1", AccrualKind.EXPENSE, Money.of(500, "USD"), DEC31, JAN1)
    accrual.reverse(JAN1)
    twice = False
    try:
        accrual.reverse(JAN1)
    except Refused:
        twice = True
    findings.append(Finding("an accrual reverses once", twice, True))

    template = RecurringTemplate(
        name="rent",
        postings=(
            debit("5000", Money.of(1000, "USD")),
            credit("1000", Money.of(1000, "USD")),
        ),
        anchor=datetime.date(2026, 1, 31),
    )
    first = template.generate(datetime.date(2026, 3, 31))
    second = template.generate(datetime.date(2026, 3, 31))
    findings.append(Finding("a recurring template generates three months", len(first), 3))
    findings.append(Finding("and nothing on a rerun", len(second), 0))
    findings.append(
        Finding(
            "the month-end anchor returns to the 31st",
            [entry.date.day for entry in first],
            [31, 28, 31],
        )
    )
    return findings
