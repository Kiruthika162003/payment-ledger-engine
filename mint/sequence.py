"""Gapless numbering: invoice numbers that never skip and never repeat.

Many tax authorities require that invoice numbers form an unbroken
sequence, because a gap is indistinguishable from a deleted
invoice and an auditor cannot tell a clerical skip from concealed
revenue. That legal requirement makes numbering a piece of ledger
logic rather than a formatting detail, and it rules out the
obvious implementations: a counter that increments on request
leaves a hole whenever the request that took a number then fails,
and a number derived from a timestamp or a row id is not gapless at
all. This module issues numbers one at a time from a counter that
only advances when the caller confirms the document was actually
recorded, so a number handed out and abandoned is returned rather
than burned. It refuses to go backward, since reissuing a number
already used would put two documents under one identity, and it
refuses to jump forward past the next value, since that is exactly
the gap the rule forbids. Numbers are formatted with a prefix and a
fixed width, so they sort lexicographically in the same order they
were issued, which is what makes a printed list of them readable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import Refused


@dataclass
class GaplessSequence:
    prefix: str = ""
    width: int = 5
    next_value: int = 1
    issued: list[int] = field(default_factory=list)
    reserved: int | None = None

    def format(self, value: int) -> str:
        return f"{self.prefix}{str(value).rjust(self.width, '0')}"

    def peek(self) -> str:
        return self.format(self.next_value)

    def reserve(self) -> str:
        if self.reserved is not None:
            raise Refused(
                f"number {self.format(self.reserved)} is already reserved and "
                "not yet confirmed; confirm or release it before reserving again"
            )
        self.reserved = self.next_value
        return self.format(self.reserved)

    def confirm(self) -> str:
        if self.reserved is None:
            raise Refused("there is no reserved number to confirm")
        value = self.reserved
        self.reserved = None
        self.issued.append(value)
        self.next_value = value + 1
        return self.format(value)

    def release(self) -> None:
        if self.reserved is None:
            raise Refused("there is no reserved number to release")
        self.reserved = None

    def issue(self) -> str:
        self.reserve()
        return self.confirm()

    def has_gaps(self) -> bool:
        if not self.issued:
            return False
        expected = range(self.issued[0], self.issued[0] + len(self.issued))
        return self.issued != list(expected)

    def count(self) -> int:
        return len(self.issued)
