"""A lending desk: affordability, the schedule, a revolving line, and the covenants.

This example runs a small commercial lending decision end to end.
An applicant is assessed for affordability today and under a stress
test, the loan is amortized so the last payment retires the balance
exactly, a revolving facility accrues interest only on the days it
was drawn, and the borrower's covenants are tested for headroom
rather than a bare pass or fail. It composes affordability,
amortization, the credit line, and the covenant suite, and every
printed line is pinned in the test suite.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.affordability import AffordabilityPolicy, assess
from mint.amortization import schedule
from mint.covenant import CovenantSuite
from mint.creditline import CreditLine
from mint.money import Money

JAN1 = datetime.date(2026, 1, 1)
JAN20 = datetime.date(2026, 1, 20)
JAN22 = datetime.date(2026, 1, 22)
FEB1 = datetime.date(2026, 2, 1)


def _dollars(money: Money) -> str:
    return money.format(with_symbol=False)


def run() -> list[str]:
    lines = ["Lending desk"]

    policy = AffordabilityPolicy(
        max_debt_to_income=Fraction(40, 100),
        stress_uplift=Fraction(3, 100),
        minimum_disposable=Money.of(500, "USD"),
    )
    result = assess(
        Money.of(50000, "USD"),
        Fraction(6, 100),
        60,
        Money.of(6000, "USD"),
        Money.of(400, "USD"),
        Money.of(2000, "USD"),
        policy,
    )
    lines.append(f"Monthly payment: {_dollars(result.monthly_payment)}")
    lines.append(f"Stressed payment: {_dollars(result.stressed_payment)}")
    lines.append(f"Verdict: {result.verdict()}")

    loan = schedule(Money.of(50000, "USD"), Fraction(6, 100), 60, 12)
    lines.append(f"Level payment: {_dollars(loan.level_payment)}")
    lines.append(f"Total interest: {_dollars(loan.total_interest())}")
    lines.append(f"Final balance: {loan.final_balance()}")
    first = loan.rows[0]
    last = loan.rows[-1]
    lines.append(f"First payment interest: {first.interest}")
    lines.append(f"Last payment interest: {last.interest}")

    line = CreditLine(
        id="RCF-1",
        limit=Money.of(100000, "USD"),
        annual_rate=Fraction(365, 10000),
    )
    line.draw(Money.of(100000, "USD"), JAN20)
    line.repay(Money.of(100000, "USD"), JAN22)
    lines.append(f"Drawn at month end: {_dollars(line.drawn(FEB1))}")
    lines.append(f"Interest for January: {_dollars(line.interest_for(JAN1, FEB1))}")

    suite = CovenantSuite(
        currency="USD",
        ebitda=Money.of(1000000, "USD"),
        net_debt=Money.of(2500000, "USD"),
        interest_expense=Money.of(250000, "USD"),
        net_worth=Money.of(500000, "USD"),
    )
    leverage = suite.test_leverage(Fraction(3))
    cover = suite.test_interest_cover(Fraction(3))
    lines.append(f"Leverage: {leverage.verdict()}")
    lines.append(f"Interest cover: {cover.verdict()}")
    lines.append(f"All covenants pass: {suite.all_pass()}")
    lines.append(f"Tightest test: {suite.tightest().name}")
    return lines


def main() -> None:
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
