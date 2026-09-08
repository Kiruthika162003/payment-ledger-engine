"""Named journals: sales, purchases, cash, and the numbering that keeps them apart.

Before everything went into one system, bookkeepers kept separate
journals for each kind of transaction, and the practice survives
because it is useful: a sales journal read on its own tells you
about sales without a month of payroll in the way, and a numbering
sequence per journal means a reference like SJ-00042 says both what
the entry was and where to find it. This module keeps that
structure. Each journal has its own gapless sequence, so a
reference is unique and unbroken within its journal, and entries
are recorded against the journal that accepted them rather than in
one undifferentiated pile. A journal can restrict which accounts it
touches, which turns a miscoded entry into an immediate refusal:
posting payroll into the sales journal is almost always a mistake,
and catching it at entry is far cheaper than finding it at close.
The journals share one ledger underneath, so the trial balance is
unaffected by how the entries were filed, which is the property
that makes the organization free.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.entry import Entry, entry
from mint.errors import Refused
from mint.ledger import Ledger
from mint.posting import Posting
from mint.sequence import GaplessSequence


@dataclass
class Journal:
    code: str
    name: str
    sequence: GaplessSequence
    allowed_accounts: frozenset[str] | None = None
    references: list[str] = field(default_factory=list)

    def accepts(self, account: str) -> bool:
        return self.allowed_accounts is None or account in self.allowed_accounts

    def guard(self, postings: list[Posting]) -> None:
        if self.allowed_accounts is None:
            return
        for posting in postings:
            if not self.accepts(posting.account):
                raise Refused(
                    f"the {self.name} does not accept postings to "
                    f"{posting.account!r}; a miscoded entry caught at entry is "
                    "far cheaper than one found at close"
                )

    def next_reference(self) -> str:
        return self.sequence.peek()

    def issue_reference(self) -> str:
        reference = self.sequence.issue()
        self.references.append(reference)
        return reference

    def count(self) -> int:
        return len(self.references)


@dataclass
class JournalSet:
    ledger: Ledger
    journals: dict[str, Journal] = field(default_factory=dict)

    def register(self, journal: Journal) -> Journal:
        if journal.code in self.journals:
            raise Refused(f"a journal coded {journal.code!r} already exists")
        self.journals[journal.code] = journal
        return journal

    def get(self, code: str) -> Journal:
        if code not in self.journals:
            raise Refused(f"there is no journal coded {code!r}")
        return self.journals[code]

    def post(
        self,
        code: str,
        postings: list[Posting],
        date: datetime.date,
        memo: str = "",
    ) -> Entry:
        journal = self.get(code)
        journal.guard(postings)
        reference = journal.issue_reference()
        built = entry(postings, date, memo=memo, ref=reference)
        return self.ledger.post(built)

    def entries_of(self, code: str) -> list[Entry]:
        journal = self.get(code)
        marks = set(journal.references)
        return [item for item in self.ledger.entries if item.ref in marks]

    def reference_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for code, journal in self.journals.items():
            for reference in journal.references:
                index[reference] = code
        return index

    def total_entries(self) -> int:
        return sum(journal.count() for journal in self.journals.values())


def standard_journals(ledger: Ledger) -> JournalSet:
    journals = JournalSet(ledger)
    for code, name in (
        ("SJ", "sales journal"),
        ("PJ", "purchase journal"),
        ("CR", "cash receipts journal"),
        ("CD", "cash disbursements journal"),
        ("GJ", "general journal"),
    ):
        journals.register(
            Journal(code=code, name=name, sequence=GaplessSequence(prefix=f"{code}-"))
        )
    return journals
