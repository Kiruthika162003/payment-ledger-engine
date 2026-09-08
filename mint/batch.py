"""Batch posting: all of it lands or none of it does, and a rejected batch says why.

Importing a day of transactions is not a hundred independent
postings; it is one operation that either succeeds or does not,
because a partially imported batch leaves the ledger in a state
nobody designed and nobody can easily unwind. The half that posted
is real, the half that did not is missing, and the operator's only
options are to hunt down which was which or to import again and
double-post everything that worked. This module removes that
choice: the batch is validated in full first, and only if every
entry is acceptable is any of it posted. Validation collects every
problem rather than stopping at the first, since an operator fixing
an import file wants the whole list, and each problem names the
entry's position in the batch so it can be found in the source. The
dry run is available on its own, which is how an import is checked
before anyone commits to it, and the posted batch reports what it
did so the operation is auditable as a unit rather than as a
scattering of unrelated entries.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from mint.entry import Entry
from mint.errors import Refused
from mint.ledger import Ledger


@dataclass(frozen=True)
class BatchProblem:
    position: int
    reason: str


@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    posted: int
    problems: tuple[BatchProblem, ...]
    committed_at: datetime.datetime | None

    def succeeded(self) -> bool:
        return not self.problems and self.committed_at is not None

    def first_problem(self) -> BatchProblem | None:
        return self.problems[0] if self.problems else None


@dataclass
class Batch:
    id: str
    entries: list[Entry] = field(default_factory=list)
    committed: bool = False

    def add(self, item: Entry) -> Entry:
        if self.committed:
            raise Refused(f"batch {self.id!r} is committed and cannot take more entries")
        self.entries.append(item)
        return item

    def size(self) -> int:
        return len(self.entries)

    def validate(self, ledger: Ledger) -> list[BatchProblem]:
        problems: list[BatchProblem] = []
        for position, item in enumerate(self.entries):
            for posting in item.postings:
                if not ledger.chart.has(posting.account):
                    problems.append(
                        BatchProblem(
                            position,
                            f"account {posting.account!r} is not in the chart",
                        )
                    )
                    continue
                account = ledger.chart.get(posting.account)
                if posting.currency != account.currency:
                    problems.append(
                        BatchProblem(
                            position,
                            f"account {posting.account!r} holds "
                            f"{account.currency} but the posting is in "
                            f"{posting.currency}",
                        )
                    )
            if not item.is_balanced():
                problems.append(BatchProblem(position, "the entry does not balance"))
        return problems

    def dry_run(self, ledger: Ledger) -> BatchResult:
        problems = self.validate(ledger)
        return BatchResult(
            batch_id=self.id,
            posted=0 if problems else len(self.entries),
            problems=tuple(problems),
            committed_at=None,
        )

    def commit(self, ledger: Ledger, at: datetime.datetime) -> BatchResult:
        if self.committed:
            raise Refused(f"batch {self.id!r} has already been committed")
        if not self.entries:
            raise Refused(f"batch {self.id!r} has nothing to post")
        problems = self.validate(ledger)
        if problems:
            # Nothing is posted, so the ledger is exactly as it was and the
            # operator can fix the file and try the whole batch again.
            return BatchResult(
                batch_id=self.id,
                posted=0,
                problems=tuple(problems),
                committed_at=None,
            )
        for item in self.entries:
            ledger.post(item)
        self.committed = True
        return BatchResult(
            batch_id=self.id,
            posted=len(self.entries),
            problems=(),
            committed_at=at,
        )
