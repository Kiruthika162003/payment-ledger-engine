"""Assay: entries exported and imported come back byte-for-byte the same.

An exchange format earns trust only if the round trip is lossless,
and the failure is usually silent: a memo dropped, a date shifted
by a timezone, a currency's minor units re-derived from a decimal
string and landing one place off. This assay exports a set of
entries that includes the awkward cases, a multi-leg split, an
amount whose cents do not divide evenly, a memo with punctuation
that a naive CSV writer would mangle, and imports the rows back,
then compares the reconstructed entries to the originals for
equality rather than for a summary that could hide a difference. It
also confirms the importer refuses a group that does not balance,
because the balance rule has to hold at every door into the ledger
and an import that accepts half a transaction is the one door that
would let the books go out of balance.
"""

from __future__ import annotations

import datetime

from mint.assays.framework import Finding, assay
from mint.entry import entry
from mint.errors import Refused
from mint.ledgerio import from_csv, import_rows, to_csv
from mint.money import Money
from mint.posting import credit, debit

DAY = datetime.date(2026, 7, 4)


def _entries():
    return [
        entry(
            [debit("1000", Money.of("99.99", "USD")), credit("4000", Money.of("99.99", "USD"))],
            DAY,
            memo='a sale, with a comma and "quotes"',
            ref="INV-1",
        ),
        entry(
            [
                debit("5000", Money.of("12.34", "USD")),
                debit("5100", Money.of("0.66", "USD")),
                credit("1000", Money.of(13, "USD")),
            ],
            DAY,
            memo="split expense",
            ref="EXP-9",
        ),
        entry(
            [debit("1500", Money.of("1000", "JPY")), credit("4500", Money.of("1000", "JPY"))],
            DAY,
            memo="a yen sale with no minor unit",
            ref="JP-1",
        ),
    ]


@assay("roundtrip", "do exported entries import back exactly as they were")
def _probe() -> list[Finding]:
    originals = _entries()
    restored = from_csv(to_csv(originals))
    findings: list[Finding] = []

    findings.append(Finding("entries restored", len(restored), len(originals)))
    findings.append(
        Finding("restored entries equal the originals", restored == originals, True)
    )

    mangled_memo = restored[0].memo if restored else ""
    findings.append(
        Finding("a memo with commas and quotes survives", mangled_memo, originals[0].memo)
    )

    yen = restored[2].postings[0].amount.units if len(restored) > 2 else -1
    findings.append(Finding("yen keep their whole units", yen, 1000))

    refused = False
    try:
        import_rows(
            [
                {
                    "group": "solo", "date": DAY.isoformat(), "memo": "", "ref": "",
                    "account": "1000", "side": "debit", "units": "500", "currency": "USD",
                }
            ]
        )
    except Refused:
        refused = True
    findings.append(Finding("an unbalanced import is refused", refused, True))
    return findings
