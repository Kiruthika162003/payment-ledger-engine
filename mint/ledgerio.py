"""Import and export: journal entries as rows, round-tripping without loss.

A ledger has to exchange entries with the world, and the exchange
format everyone actually uses is a flat table of postings, one row
per leg, with the entry identified by a shared reference. Flattening
loses nothing as long as the reassembly is careful, and this module
is written around proving that: exporting a set of entries and
importing the rows back produces entries equal to the originals,
including their dates, memos, references, and the exact minor units
of every posting. The round trip is the specification, and the
assay measures it rather than trusting it. Amounts cross the
boundary as integer minor units and a currency code rather than a
formatted decimal, because a decimal string reintroduces the
question of how many places a currency has and invites a parser to
guess. Rows that do not reassemble into a balanced entry are
refused at import with the group named, since importing half a
transaction is how a ledger silently goes out of balance, and the
whole point of the balance rule is that it is enforced at every
door, including this one.
"""

from __future__ import annotations

import csv
import datetime
import io

from mint.accounts import Side
from mint.entry import Entry, entry
from mint.errors import Refused
from mint.money import Money
from mint.posting import Posting

HEADER = ["group", "date", "memo", "ref", "account", "side", "units", "currency"]


def export_rows(entries: list[Entry]) -> list[list[str]]:
    rows: list[list[str]] = []
    for index, item in enumerate(entries):
        for posting in item.postings:
            rows.append(
                [
                    str(index),
                    item.date.isoformat(),
                    item.memo,
                    item.ref,
                    posting.account,
                    posting.side.value,
                    str(posting.amount.units),
                    posting.currency,
                ]
            )
    return rows


def to_csv(entries: list[Entry]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(export_rows(entries))
    return buffer.getvalue()


def _row_to_posting(row: dict[str, str]) -> Posting:
    try:
        units = int(row["units"])
    except (KeyError, ValueError) as exc:
        raise Refused(f"row {row!r} has no readable minor-unit amount") from exc
    side_text = row.get("side", "")
    if side_text not in (Side.DEBIT.value, Side.CREDIT.value):
        raise Refused(f"row {row!r} names side {side_text!r}, not debit or credit")
    side = Side.DEBIT if side_text == Side.DEBIT.value else Side.CREDIT
    return Posting(row["account"], Money.from_minor(units, row["currency"]), side)


def import_rows(rows: list[dict[str, str]]) -> list[Entry]:
    groups: dict[str, list[dict[str, str]]] = {}
    order: list[str] = []
    for row in rows:
        key = row.get("group", "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    entries: list[Entry] = []
    for key in order:
        members = groups[key]
        head = members[0]
        postings = [_row_to_posting(row) for row in members]
        try:
            entries.append(
                entry(
                    postings,
                    datetime.date.fromisoformat(head["date"]),
                    memo=head.get("memo", ""),
                    ref=head.get("ref", ""),
                )
            )
        except Refused as exc:
            raise Refused(f"group {key!r} does not reassemble: {exc}") from exc
    return entries


def from_csv(text: str) -> list[Entry]:
    reader = csv.DictReader(io.StringIO(text))
    return import_rows(list(reader))
