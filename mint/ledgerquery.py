"""Querying the ledger: filters that compose, so a question is asked once.

The ledger holds entries and folds them into balances, but the
questions people actually ask sit between the two: every posting to
this account, over this range of dates, above this amount, tagged
this way. Writing each of those as its own loop produces a dozen
near-identical functions that drift apart, so this module makes the
filters compose. A query is built by adding criteria and then run
once, and because each criterion is a predicate the combination is
an and of all of them, which is what people mean when they list
conditions. The result carries both the matching entries and their
total, since a query that returns rows without a total invites the
caller to sum them again in a way that may disagree. An empty
result is a legitimate answer and is reported as such rather than
raising, because finding nothing is often the point of the search,
but a query with no criteria at all is refused, since returning the
whole ledger by accident is rarely what anyone meant to ask.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field

from mint.entry import Entry
from mint.errors import Refused
from mint.ledger import Ledger
from mint.money import Money


@dataclass(frozen=True)
class QueryResult:
    entries: tuple[Entry, ...]
    currency: str

    def count(self) -> int:
        return len(self.entries)

    def is_empty(self) -> bool:
        return not self.entries

    def total_debits(self) -> Money:
        units = sum(
            posting.debit_units()
            for entry in self.entries
            for posting in entry.postings
            if posting.currency == self.currency
        )
        return Money.from_minor(units, self.currency)

    def total_credits(self) -> Money:
        units = sum(
            posting.credit_units()
            for entry in self.entries
            for posting in entry.postings
            if posting.currency == self.currency
        )
        return Money.from_minor(units, self.currency)

    def dates(self) -> tuple[datetime.date, ...]:
        return tuple(sorted({entry.date for entry in self.entries}))

    def refs(self) -> tuple[str, ...]:
        return tuple(sorted({entry.ref for entry in self.entries if entry.ref}))


@dataclass
class Query:
    currency: str
    criteria: list[tuple[str, Callable[[Entry], bool]]] = field(default_factory=list)

    def _add(self, label: str, predicate: Callable[[Entry], bool]) -> Query:
        self.criteria.append((label, predicate))
        return self

    def touching(self, account: str) -> Query:
        return self._add(f"touching {account}", lambda entry: entry.touches(account))

    def between(self, start: datetime.date, end: datetime.date) -> Query:
        if end < start:
            raise Refused("a date range ends after it begins")
        return self._add(
            f"between {start.isoformat()} and {end.isoformat()}",
            lambda entry: start <= entry.date <= end,
        )

    def tagged(self, tag: str) -> Query:
        return self._add(f"tagged {tag}", lambda entry: tag in entry.tags)

    def referenced(self, ref: str) -> Query:
        return self._add(f"ref {ref}", lambda entry: entry.ref == ref)

    def memo_contains(self, needle: str) -> Query:
        lowered = needle.lower()
        return self._add(
            f"memo contains {needle!r}",
            lambda entry: lowered in entry.memo.lower(),
        )

    def at_least(self, amount: Money) -> Query:
        def predicate(entry: Entry) -> bool:
            return entry.debit_total(amount.currency) >= amount.units

        return self._add(f"at least {amount.format()}", predicate)

    def at_most(self, amount: Money) -> Query:
        def predicate(entry: Entry) -> bool:
            return entry.debit_total(amount.currency) <= amount.units

        return self._add(f"at most {amount.format()}", predicate)

    def describe(self) -> str:
        return " and ".join(label for label, _ in self.criteria)

    def run(self, ledger: Ledger) -> QueryResult:
        if not self.criteria:
            raise Refused(
                "a query with no criteria returns the whole ledger, which is "
                "rarely what anyone meant to ask"
            )
        matched = [
            entry
            for entry in ledger.entries
            if all(predicate(entry) for _, predicate in self.criteria)
        ]
        return QueryResult(entries=tuple(matched), currency=self.currency)


def query(currency: str) -> Query:
    return Query(currency=currency)
