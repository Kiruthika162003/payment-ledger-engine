"""Payment files: instructions to a bank, with the control totals that prove them intact.

A payment file tells a bank to move money, so the risk is not that
it fails but that it succeeds after being altered or truncated. The
defence banks settled on decades ago is the control total: the file
carries a count of the instructions and the sum of their amounts,
and the bank recomputes both before acting. A file that lost a line
in transit fails the count; one whose amounts were tampered with
fails the sum. This module builds files with those totals and, more
usefully, verifies them, because generating a control total is
trivial and checking one is the part that actually protects
anything. Duplicate instruction references are refused at build
time, since a bank presented with the same reference twice may pay
twice, and a file with no instructions is refused rather than sent,
because an empty payment run almost always means an upstream
failure that nobody noticed. The rendered form is deliberately
plain text with a header, body, and trailer, the shape these files
have had since they were written to tape.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Instruction:
    reference: str
    beneficiary: str
    account: str
    amount: Money

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise Refused("a payment instruction needs a reference")
        if not self.beneficiary.strip():
            raise Refused("a payment instruction names a beneficiary")
        if not self.amount.is_positive():
            raise Refused("a payment instruction moves a positive amount")


@dataclass
class PaymentFile:
    file_id: str
    currency: str
    value_date: datetime.date
    debit_account: str
    instructions: list[Instruction] = field(default_factory=list)

    def add(
        self, reference: str, beneficiary: str, account: str, amount: Money
    ) -> Instruction:
        if amount.currency != self.currency:
            raise Refused(
                f"instruction {reference!r} is in {amount.currency}, not the "
                f"file currency {self.currency}"
            )
        if any(item.reference == reference for item in self.instructions):
            raise Refused(
                f"reference {reference!r} is already in this file; a bank "
                "presented with the same reference twice may pay twice"
            )
        instruction = Instruction(reference, beneficiary, account, amount)
        self.instructions.append(instruction)
        return instruction

    def count(self) -> int:
        return len(self.instructions)

    def control_total(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.instructions:
            total = total + item.amount
        return total

    def render(self) -> list[str]:
        if not self.instructions:
            raise Refused(
                f"file {self.file_id!r} has no instructions; an empty payment "
                "run almost always means an upstream failure nobody noticed"
            )
        lines = [
            f"HDR|{self.file_id}|{self.value_date.isoformat()}|"
            f"{self.debit_account}|{self.currency}"
        ]
        for item in self.instructions:
            lines.append(
                f"PMT|{item.reference}|{item.beneficiary}|{item.account}|"
                f"{item.amount.units}"
            )
        lines.append(f"TRL|{self.count()}|{self.control_total().units}")
        return lines

    def to_text(self) -> str:
        return "\n".join(self.render())


@dataclass(frozen=True)
class VerificationResult:
    file_id: str
    counted: int
    declared_count: int
    summed: int
    declared_total: int

    def count_matches(self) -> bool:
        return self.counted == self.declared_count

    def total_matches(self) -> bool:
        return self.summed == self.declared_total

    def is_intact(self) -> bool:
        return self.count_matches() and self.total_matches()

    def problem(self) -> str | None:
        if not self.count_matches():
            return (
                f"the file declares {self.declared_count} instructions but "
                f"carries {self.counted}; a line was lost or added"
            )
        if not self.total_matches():
            return (
                f"the file declares a total of {self.declared_total} but the "
                f"instructions sum to {self.summed}; an amount was altered"
            )
        return None


def verify(text: str) -> VerificationResult:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("HDR|"):
        raise Refused("a payment file starts with a header record")
    if not lines[-1].startswith("TRL|"):
        raise Refused("a payment file ends with a trailer record")
    header = lines[0].split("|")
    trailer = lines[-1].split("|")
    if len(trailer) != 3:
        raise Refused("the trailer record is malformed")
    body = lines[1:-1]
    counted = 0
    summed = 0
    for line in body:
        parts = line.split("|")
        if parts[0] != "PMT" or len(parts) != 5:
            raise Refused(f"the record {line!r} is not a payment instruction")
        counted += 1
        summed += int(parts[4])
    return VerificationResult(
        file_id=header[1],
        counted=counted,
        declared_count=int(trailer[1]),
        summed=summed,
        declared_total=int(trailer[2]),
    )
