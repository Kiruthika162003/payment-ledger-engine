"""mint: a double-entry payment ledger where every posting balances.

The package is organized in layers from the bottom up. Money and
currency sit at the base, storing amounts as whole minor units so
arithmetic is exact. Above them are accounts and the chart that
organizes them, then postings and the balanced journal entries
that group postings, then the ledger that records entries and the
book that holds many ledgers. On top of that core sit the payment
flows, authorizations and captures, refunds and disputes,
idempotent posting, and the reporting that turns a pile of entries
back into statements a person can read. The assays package is the
verification organ: measured claims about invariants that either
hold as numbers or fail loudly.
"""

from __future__ import annotations

__version__ = "0.1.0"
