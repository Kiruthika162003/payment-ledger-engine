"""Assay: what a merchant is shown as payable is what they can actually be paid.

A merchant's dashboard shows several balances and only one of them
is money they can have today. Gross sales is what customers paid,
available is what survives refunds, fees, and chargebacks, and
payable is what is left after the reserve and the settlement delay.
Conflating any two of them produces a support ticket every payout
day, and the specific bug that produces the worst one is treating a
reserve hold as though it had removed money from available, so
releasing it later credits the merchant twice. This assay measures
the three balances apart, confirms a hold and its release net to
nothing, and confirms a payout takes exactly the payable figure and
leaves it at zero. The payout date is measured too, since a
merchant told to expect funds on a Saturday concludes something has
gone wrong when they arrive on Tuesday.
"""

from __future__ import annotations

import datetime

from mint.assays.framework import Finding, assay
from mint.merchantaccount import MerchantAccount
from mint.money import Money
from mint.payoutschedule import Cadence, PayoutSchedule

DAY1 = datetime.date(2026, 5, 1)
DAY10 = datetime.date(2026, 5, 10)
FRIDAY = datetime.date(2026, 1, 2)


def _account() -> MerchantAccount:
    account = MerchantAccount(merchant_id="M-1", currency="USD")
    account.sale(Money.of(1000, "USD"), DAY1, "order-1")
    account.fee(Money.of("29.00", "USD"), DAY1)
    account.refund(Money.of(100, "USD"), DAY1, "order-1")
    account.chargeback(Money.of(50, "USD"), DAY1, "order-9")
    return account


@assay("payouts", "is the payable figure the one a merchant can actually be paid")
def _probe() -> list[Finding]:
    findings: list[Finding] = []

    account = _account()
    findings.append(Finding("gross sales", account.gross_sales(DAY10).units, 100000))
    findings.append(
        Finding(
            "available after deductions",
            account.available_balance(DAY10).units,
            82100,
        )
    )

    account.hold_reserve(Money.of(200, "USD"), DAY1)
    findings.append(Finding("a reserve does not change available",
                            account.available_balance(DAY10).units, 82100))
    findings.append(Finding("but it does reduce payable",
                            account.payable_balance(DAY10).units, 62100))

    account.release_reserve(Money.of(200, "USD"), DAY1)
    findings.append(Finding("a hold and its release net to nothing",
                            account.available_balance(DAY10).units, 82100))
    findings.append(Finding("payable is restored", account.payable_balance(DAY10).units, 82100))

    paid = account.pay_out(DAY10)
    findings.append(Finding("the payout takes the payable figure", paid.units, 82100))
    findings.append(Finding("and leaves nothing payable",
                            account.payable_balance(DAY10).units, 0))

    schedule = PayoutSchedule(cadence=Cadence.DAILY, delay_days=2)
    landing = schedule.payout_for_sale(FRIDAY)
    findings.append(
        Finding("a Friday sale lands on a banking day", landing.weekday() < 5, True)
    )
    findings.append(Finding("days from sale to money", schedule.days_to_money(FRIDAY), 4))
    return findings
