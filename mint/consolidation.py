"""Consolidation: adding up the group, then taking out what it owes itself.

Consolidating a group is three steps in a fixed order, and the
order is what makes it correct. First combine the controlled
entities line by line at one hundred percent, because control means
the parent directs all of those assets even if it owns only part of
them. Second eliminate intercompany balances, since a group cannot
owe itself money and leaving those in inflates both sides. Third
recognize the minority interest, the share of a subsidiary's equity
belonging to owners outside the group, which is what makes
consolidating at a hundred percent honest rather than overstating
what the parent's shareholders own. This module performs the three
steps and reports each so a reviewer can see the combination, the
elimination, and the minority separately rather than a single
number they have to trust. Entities the parent does not control are
excluded from combination entirely rather than partly included,
because line-by-line consolidation of something you do not direct
misrepresents the group, and their value belongs in an investment
line instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from mint.entity import Group
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


@dataclass(frozen=True)
class EntityFigures:
    code: str
    assets: Money
    liabilities: Money
    equity: Money
    revenue: Money

    def balances(self) -> bool:
        return self.assets == self.liabilities + self.equity


@dataclass(frozen=True)
class Consolidated:
    currency: str
    combined_assets: Money
    combined_liabilities: Money
    combined_equity: Money
    combined_revenue: Money
    eliminated: Money
    minority_interest: Money
    included: tuple[str, ...]
    excluded: tuple[str, ...]

    def group_assets(self) -> Money:
        return self.combined_assets - self.eliminated

    def group_liabilities(self) -> Money:
        return self.combined_liabilities - self.eliminated

    def parent_equity(self) -> Money:
        return self.combined_equity - self.minority_interest

    def balances(self) -> bool:
        equity = self.parent_equity() + self.minority_interest
        return self.group_assets() == self.group_liabilities() + equity


def consolidate(
    group: Group,
    parent: str,
    figures: dict[str, EntityFigures],
    currency: str,
    intercompany: Money | None = None,
) -> Consolidated:
    currency = currency.upper()
    group.get(parent)
    if parent not in figures:
        raise Refused(f"no figures were supplied for the parent {parent!r}")

    zero = Money.zero(currency)
    combined_assets = zero
    combined_liabilities = zero
    combined_equity = zero
    combined_revenue = zero
    minority = zero
    included: list[str] = []
    excluded: list[str] = []

    for code in [parent, *group.children_of(parent)]:
        if code not in figures:
            raise Refused(f"no figures were supplied for entity {code!r}")
        item = figures[code]
        if item.assets.currency != currency:
            raise Refused(
                f"entity {code!r} reports in {item.assets.currency}; translate "
                f"it to {currency} before consolidating"
            )
        if code != parent and not group.controls(parent, code):
            excluded.append(code)
            continue
        included.append(code)
        combined_assets = combined_assets + item.assets
        combined_liabilities = combined_liabilities + item.liabilities
        combined_equity = combined_equity + item.equity
        combined_revenue = combined_revenue + item.revenue
        if code != parent:
            share = group.minority_share(parent, code)
            minority = minority + scale(item.equity, share, Rounding.HALF_EVEN)

    return Consolidated(
        currency=currency,
        combined_assets=combined_assets,
        combined_liabilities=combined_liabilities,
        combined_equity=combined_equity,
        combined_revenue=combined_revenue,
        eliminated=intercompany or zero,
        minority_interest=minority,
        included=tuple(included),
        excluded=tuple(excluded),
    )


def ownership_weighted(amount: Money, share: Fraction) -> Money:
    return scale(amount, share, Rounding.HALF_EVEN)
