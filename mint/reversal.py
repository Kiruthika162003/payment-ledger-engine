"""Reversals: undoing an entry by posting its mirror, never by deleting it.

A ledger does not edit history, so the only honest way to undo an
entry is to post another one that cancels it, and the cancelling
entry is the original with every posting flipped from debit to
credit and back. This module builds that mirror. The reversal keeps
the original's amounts and accounts exactly and changes only the
sides, so the pair nets to nothing on every account it touched,
which is the property that makes an undo provable rather than
asserted. It carries the original's reference so the two can be
found together, because a reversal that cannot be tied to what it
reversed leaves an auditor with two mysterious entries instead of
one corrected transaction. A reversal is dated on the day the
correction is made rather than the day of the original, since
backdating the fix would restate a period that has already been
reported, and the caller who genuinely wants the original period
must say so explicitly. Reversing a reversal is allowed and simply
restores the original effect, which is what someone who reversed by
mistake actually needs.
"""

from __future__ import annotations

import datetime

from mint.entry import Entry, entry
from mint.errors import Refused
from mint.posting import Posting


def reverse_postings(postings: tuple[Posting, ...]) -> list[Posting]:
    return [posting.flip() for posting in postings]


def reverse_entry(original: Entry, on: datetime.date, memo: str | None = None) -> Entry:
    if on < original.date:
        raise Refused(
            "a reversal dated before its original would restate a period that "
            "has already been reported; date it on the day of the correction"
        )
    if memo is not None:
        label = memo
    elif original.memo:
        label = f"reversal of {original.memo}"
    else:
        label = "reversal"
    return entry(
        reverse_postings(original.postings),
        on,
        memo=label,
        ref=original.ref,
        tags=frozenset({*original.tags, "reversal"}),
    )


def nets_to_zero(original: Entry, reversal: Entry) -> bool:
    net: dict[tuple[str, str], int] = {}
    for source in (original, reversal):
        for posting in source.postings:
            key = (posting.account, posting.currency)
            net[key] = net.get(key, 0) + posting.debit_units() - posting.credit_units()
    return all(value == 0 for value in net.values())
