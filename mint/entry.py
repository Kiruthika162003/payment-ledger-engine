"""Journal entries: a bundle of postings that must sum to zero per currency.

The single rule that makes double entry trustworthy is that the
debits and the credits of an entry are equal, because if they are,
then no entry can create or destroy money, only move it, and the
whole ledger inherits that property by induction. This module
enforces the rule at construction: an entry validates the moment
it is built and refuses to exist unbalanced, so no other code ever
has to defend against an invalid entry in its hands. The balance
is checked per currency rather than in aggregate, since an entry
that debits a hundred dollars and credits ninety euros is not
balanced just because the numbers happen to look close, and a
genuine multi-currency entry balances within each currency
separately with the exchange difference carried on its own
posting. An entry with no postings is refused as empty, and an
entry with postings in only one direction is caught by the
balance check, since a lone debit cannot sum to zero against
nothing. The entry carries a date and a memo because a movement of
money that cannot say when it happened or why is a movement an
auditor cannot follow, and following the money is the entire job.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from mint.errors import Unbalanced
from mint.posting import Posting


@dataclass(frozen=True)
class Entry:
    postings: tuple[Posting, ...]
    date: datetime.date
    memo: str = ""
    ref: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.postings:
            raise Unbalanced("an entry with no postings records nothing")
        imbalance = self.imbalance()
        if imbalance:
            parts = ", ".join(
                f"{currency} off by {net}" for currency, net in sorted(imbalance.items())
            )
            raise Unbalanced(
                f"the entry does not balance: {parts}; debits and credits "
                "must be equal within each currency"
            )

    def imbalance(self) -> dict[str, int]:
        net: dict[str, int] = defaultdict(int)
        for posting in self.postings:
            net[posting.currency] += posting.debit_units() - posting.credit_units()
        return {currency: value for currency, value in net.items() if value != 0}

    def is_balanced(self) -> bool:
        return not self.imbalance()

    def currencies(self) -> list[str]:
        return sorted({posting.currency for posting in self.postings})

    def accounts(self) -> list[str]:
        return sorted({posting.account for posting in self.postings})

    def touches(self, account: str) -> bool:
        return any(posting.account == account for posting in self.postings)

    def debit_total(self, currency: str) -> int:
        return sum(p.debit_units() for p in self.postings if p.currency == currency)

    def credit_total(self, currency: str) -> int:
        return sum(p.credit_units() for p in self.postings if p.currency == currency)

    def postings_for(self, account: str) -> tuple[Posting, ...]:
        return tuple(p for p in self.postings if p.account == account)


def entry(
    postings: list[Posting],
    date: datetime.date,
    memo: str = "",
    ref: str = "",
    tags: frozenset[str] | None = None,
) -> Entry:
    return Entry(
        postings=tuple(postings),
        date=date,
        memo=memo,
        ref=ref,
        tags=tags if tags is not None else frozenset(),
    )
