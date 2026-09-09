"""The assay registry: import every assay module so it registers itself.

Importing this package is what populates the catalog. Each assay
module registers its probe as a side effect of being imported, so
this file's job is simply to import them all in a stable order and
re-export the framework's query functions. Adding an assay means
writing its module and adding one import line here, which keeps the
registry a single readable list rather than a discovery mechanism
that hides which claims are actually being checked.
"""

from __future__ import annotations

from mint.assays import (  # noqa: F401
    allocation,
    balance,
    closing,
    conservation,
    controls,
    controls_of_duty,
    custody,
    fx,
    lifecycle,
    netting,
    payouts,
    periods,
    pricing,
    provisions,
    recognition,
    reconciliation,
    roundtrip,
    schedules,
    statements,
    tamper,
)
from mint.assays.framework import Assay, Finding, assay, broken, catalog

__all__ = ["Assay", "Finding", "assay", "broken", "catalog"]
