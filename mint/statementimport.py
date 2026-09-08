"""Importing a bank statement: every bank's format is different, so the mapping is data.

No two banks export the same columns, and the ones that share names
disagree about what they mean: one bank signs withdrawals negative
in a single amount column, another uses separate debit and credit
columns, and a third puts the running balance where you expect the
amount. Hardcoding one layout means a new bank is a code change, so
this module takes the column mapping as data and validates it
against the header before reading a single row. Rows that cannot be
parsed are collected with their line numbers rather than aborting
the import, because a statement with three bad rows out of four
hundred should surface those three rather than refusing everything,
and the caller decides whether to proceed. The one thing it will
not do is guess: a row whose amount cannot be read is reported, not
defaulted to zero, since a zero-value transaction in a bank import
is indistinguishable from a real one that failed to parse and will
quietly break the reconciliation instead.
"""

from __future__ import annotations

import csv
import datetime
import io
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class ColumnMap:
    date: str
    description: str
    amount: str | None = None
    debit: str | None = None
    credit: str | None = None
    date_format: str = "%Y-%m-%d"
    debits_are_negative: bool = True

    def __post_init__(self) -> None:
        has_single = self.amount is not None
        has_pair = self.debit is not None and self.credit is not None
        if has_single == has_pair:
            raise Refused(
                "a column map names either one amount column or a debit and a "
                "credit column, not both and not neither"
            )

    def required(self) -> list[str]:
        names = [self.date, self.description]
        if self.amount is not None:
            names.append(self.amount)
        else:
            names.extend([self.debit, self.credit])
        return names


@dataclass(frozen=True)
class StatementLine:
    row: int
    date: datetime.date
    description: str
    amount: Money

    def is_credit(self) -> bool:
        return self.amount.is_positive()


@dataclass(frozen=True)
class RowProblem:
    row: int
    reason: str


@dataclass
class ImportResult:
    lines: list[StatementLine] = field(default_factory=list)
    problems: list[RowProblem] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not self.problems

    def total(self, currency: str) -> Money:
        total = Money.zero(currency)
        for line in self.lines:
            total = total + line.amount
        return total

    def credits(self) -> list[StatementLine]:
        return [line for line in self.lines if line.is_credit()]

    def debits(self) -> list[StatementLine]:
        return [line for line in self.lines if not line.is_credit()]


def _parse_amount(text: str, currency: str) -> Money:
    cleaned = text.strip().replace(",", "").replace("(", "-").replace(")", "")
    if not cleaned:
        raise ValueError("blank")
    return Money.of(cleaned, currency)


def import_statement(
    text: str, mapping: ColumnMap, currency: str
) -> ImportResult:
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [name for name in mapping.required() if name not in header]
    if missing:
        raise Refused(
            f"the statement is missing the column(s) {missing}; the mapping "
            "describes a different export than this file"
        )

    result = ImportResult()
    for index, row in enumerate(reader, start=2):
        try:
            when = datetime.datetime.strptime(
                row[mapping.date].strip(), mapping.date_format
            ).date()
        except (ValueError, AttributeError):
            result.problems.append(
                RowProblem(index, f"the date {row.get(mapping.date)!r} is unreadable")
            )
            continue
        try:
            if mapping.amount is not None:
                amount = _parse_amount(row[mapping.amount], currency)
                if not mapping.debits_are_negative:
                    amount = -amount
            else:
                debit_text = (row.get(mapping.debit) or "").strip()
                credit_text = (row.get(mapping.credit) or "").strip()
                if debit_text and credit_text:
                    raise ValueError("both sides populated")
                if debit_text:
                    amount = -_parse_amount(debit_text, currency)
                elif credit_text:
                    amount = _parse_amount(credit_text, currency)
                else:
                    raise ValueError("neither side populated")
        except (ValueError, Refused) as exc:
            # Never defaulted to zero: a zero row is indistinguishable from a
            # real one that failed to parse and breaks the reconciliation.
            result.problems.append(
                RowProblem(index, f"the amount could not be read: {exc}")
            )
            continue
        result.lines.append(
            StatementLine(
                row=index,
                date=when,
                description=(row.get(mapping.description) or "").strip(),
                amount=amount,
            )
        )
    return result


SINGLE_COLUMN = ColumnMap(date="Date", description="Description", amount="Amount")
TWO_COLUMN = ColumnMap(
    date="Date", description="Narrative", debit="Debit", credit="Credit"
)
