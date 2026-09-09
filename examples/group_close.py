"""A group close: translate a subsidiary, eliminate what the group owes itself, consolidate.

This example performs the consolidation a group finance team runs
each quarter. A foreign subsidiary's statements are translated at
three different rates, with the residual falling to the cumulative
translation adjustment; the intercompany balances are checked for
reciprocity before anything is eliminated; and the group is
consolidated at full value with the outside shareholders' share
recognized as minority interest. It composes translation,
intercompany, and consolidation with the entity structure, and
every printed line is pinned in the test suite.
"""

from __future__ import annotations

from fractions import Fraction

from mint.consolidation import EntityFigures, consolidate
from mint.entity import Entity, Group
from mint.intercompany import IntercompanyLedger
from mint.money import Money
from mint.translation import ForeignStatements, translate


def _dollars(money: Money) -> str:
    return money.format(with_symbol=False)


def run() -> list[str]:
    lines = ["Group close"]

    group = Group()
    group.add(Entity("P", "Parent Inc", "USD"))
    group.add(Entity("S", "Sub GmbH", "EUR"))
    group.add(Entity("A", "Associate Ltd", "USD"))
    group.own("P", "S", Fraction(60, 100))
    group.own("P", "A", Fraction(30, 100))
    lines.append(f"Controlled subsidiaries: {group.controlled_subsidiaries('P')}")
    lines.append(f"Minority share of the sub: {group.minority_share('P', 'S')}")

    foreign = ForeignStatements(
        assets=Money.of(1000, "EUR"),
        liabilities=Money.of(400, "EUR"),
        contributed_equity=Money.of(500, "EUR"),
        retained_earnings=Money.of(100, "EUR"),
        revenue=Money.of(800, "EUR"),
        expenses=Money.of(700, "EUR"),
    )
    lines.append(f"Subsidiary balances in its own currency: {foreign.balances()}")
    translated = translate(
        foreign, "USD", Fraction(12, 10), Fraction(11, 10), Fraction(1)
    )
    lines.append(f"Translated assets: {_dollars(translated.assets)}")
    lines.append(f"Translated revenue: {_dollars(translated.revenue)}")
    lines.append(
        f"Translation adjustment: {_dollars(translated.translation_adjustment)}"
    )
    lines.append(f"Translated statements balance: {translated.balances()}")

    intercompany = IntercompanyLedger("USD")
    intercompany.record("P", "S", Money.of(100, "USD"), "receivable")
    intercompany.record("S", "P", Money.of(100, "USD"), "payable")
    lines.append(f"Intercompany reciprocal: {intercompany.is_reciprocal()}")
    lines.append(f"Eliminable: {_dollars(intercompany.eliminable())}")

    figures = {
        "P": EntityFigures(
            "P", Money.of(5000, "USD"), Money.of(2000, "USD"),
            Money.of(3000, "USD"), Money.of(4000, "USD"),
        ),
        "S": EntityFigures(
            "S", translated.assets, translated.liabilities,
            translated.total_equity(), translated.revenue,
        ),
        "A": EntityFigures(
            "A", Money.of(900, "USD"), Money.of(400, "USD"),
            Money.of(500, "USD"), Money.of(700, "USD"),
        ),
    }
    result = consolidate(
        group, "P", figures, "USD", intercompany=intercompany.eliminable()
    )
    lines.append(f"Included: {list(result.included)}")
    lines.append(f"Excluded as not controlled: {list(result.excluded)}")
    lines.append(f"Group assets after elimination: {_dollars(result.group_assets())}")
    lines.append(f"Minority interest: {_dollars(result.minority_interest)}")
    lines.append(f"Parent equity: {_dollars(result.parent_equity())}")
    lines.append(f"Consolidated sheet balances: {result.balances()}")
    return lines


def main() -> None:
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
