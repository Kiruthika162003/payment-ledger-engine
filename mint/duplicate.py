"""Duplicate payments: catching the invoice that got paid twice, without crying wolf.

Paying the same invoice twice is the most common and most
recoverable loss in accounts payable, and it happens because the
second copy arrives looking slightly different: the invoice number
gains a prefix, the date shifts, a scanning system drops a leading
zero. A detector that demands exact equality catches almost none of
them, and one that flags every same-amount payment to a vendor
buries the real hits under a month of rent and payroll. This module
scores candidate pairs on several signals at once, the same vendor,
the same amount, a date within a window, and a normalized invoice
number that matches after stripping punctuation and leading zeros,
and reports the signals that fired rather than a bare verdict, so a
reviewer sees why a pair was raised and can dismiss it quickly.
Recurring payments are the main false positive, so a pair whose
dates fall almost exactly a month or a period apart is downgraded,
because a payment that repeats on schedule is a subscription rather
than a mistake, and treating the two the same is what teaches
people to ignore the report.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class PaymentRecord:
    id: str
    vendor: str
    amount: Money
    date: datetime.date
    invoice_number: str = ""


@dataclass(frozen=True)
class DuplicateCandidate:
    left: str
    right: str
    signals: tuple[str, ...]
    score: int
    likely_recurring: bool

    def is_strong(self) -> bool:
        return self.score >= 3 and not self.likely_recurring


def normalize_invoice(number: str) -> str:
    # Leading zeros are stripped within each run of digits, not just at the
    # front of the string, so INV-000123 and inv123 normalize alike; a
    # whole-string lstrip leaves the zeros untouched behind a letter prefix.
    kept = "".join(char for char in number if char.isalnum()).upper()
    out: list[str] = []
    for run in re.findall(r"\d+|\D+", kept):
        if run.isdigit():
            out.append(run.lstrip("0") or "0")
        else:
            out.append(run)
    return "".join(out) or kept


def _looks_recurring(left: PaymentRecord, right: PaymentRecord) -> bool:
    gap = abs((right.date - left.date).days)
    # A payment repeating near a month or a quarter apart is a schedule,
    # not a slip, and flagging it teaches people to ignore the report.
    return any(abs(gap - period) <= 3 for period in (28, 30, 31, 90, 91, 365))


def compare(
    left: PaymentRecord, right: PaymentRecord, window_days: int = 30
) -> DuplicateCandidate:
    signals: list[str] = []
    if left.vendor == right.vendor:
        signals.append("same vendor")
    if left.amount == right.amount:
        signals.append("same amount")
    if abs((right.date - left.date).days) <= window_days:
        signals.append("dates within the window")
    if (
        left.invoice_number
        and normalize_invoice(left.invoice_number) == normalize_invoice(right.invoice_number)
    ):
        signals.append("matching invoice number")
    return DuplicateCandidate(
        left=left.id,
        right=right.id,
        signals=tuple(signals),
        score=len(signals),
        likely_recurring=_looks_recurring(left, right),
    )


def scan(
    payments: list[PaymentRecord], window_days: int = 30, minimum_score: int = 3
) -> list[DuplicateCandidate]:
    if minimum_score < 1:
        raise Refused(
            "a duplicate scan needs at least one matching signal; a threshold "
            "of zero flags every pair in the ledger"
        )
    found: list[DuplicateCandidate] = []
    for index, left in enumerate(payments):
        for right in payments[index + 1 :]:
            candidate = compare(left, right, window_days)
            if candidate.score >= minimum_score:
                found.append(candidate)
    return found


def strong_candidates(candidates: list[DuplicateCandidate]) -> list[DuplicateCandidate]:
    return [item for item in candidates if item.is_strong()]
