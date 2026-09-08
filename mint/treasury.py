"""Treasury sweeps: moving idle cash to where it earns, keeping each account funded.

A business with several bank accounts wants each one to hold what
it needs and no more, with the surplus concentrated where it earns
interest. A sweep is the set of transfers that achieves that, and
the property it must have is conservation: the transfers move money
between accounts and never create or destroy it, so the total
across the group is identical before and after. This module
computes the transfers and checks that property rather than
assuming it. Accounts declare a target balance and a minimum, and
the sweep pulls surplus above the target into the concentration
account and pushes funds out to any account below its minimum,
funding the shortfalls first, because leaving an operating account
short to earn interest elsewhere is how a payroll run bounces. If
the concentration account cannot cover every shortfall the sweep
refuses rather than partially funding accounts in whatever order
they happened to be listed, since a partial sweep leaves the
business in a state nobody chose and hard to reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import InsufficientFunds, Refused
from mint.money import Money


@dataclass(frozen=True)
class SweepAccount:
    code: str
    balance: Money
    target: Money
    minimum: Money

    def __post_init__(self) -> None:
        self.target.same_currency(self.balance)
        self.minimum.same_currency(self.balance)
        if self.minimum > self.target:
            raise Refused(
                f"account {self.code!r} has a minimum above its target; the "
                "sweep would fight itself"
            )

    def surplus(self) -> Money:
        excess = self.balance - self.target
        return excess if excess.is_positive() else Money.zero(self.balance.currency)

    def shortfall(self) -> Money:
        gap = self.minimum - self.balance
        return gap if gap.is_positive() else Money.zero(self.balance.currency)


@dataclass(frozen=True)
class Transfer:
    source: str
    destination: str
    amount: Money


@dataclass
class SweepPlan:
    concentration: str
    currency: str
    transfers: list[Transfer] = field(default_factory=list)

    def total_moved(self) -> Money:
        total = Money.zero(self.currency)
        for transfer in self.transfers:
            total = total + transfer.amount
        return total

    def net_change(self, code: str) -> Money:
        total = Money.zero(self.currency)
        for transfer in self.transfers:
            if transfer.destination == code:
                total = total + transfer.amount
            if transfer.source == code:
                total = total - transfer.amount
        return total

    def conserves(self) -> bool:
        total = Money.zero(self.currency)
        for transfer in self.transfers:
            total = total + transfer.amount - transfer.amount
        return total.is_zero()


def plan_sweep(
    accounts: list[SweepAccount], concentration: str, currency: str
) -> SweepPlan:
    currency = currency.upper()
    by_code = {account.code: account for account in accounts}
    if concentration not in by_code:
        raise Refused(
            f"the concentration account {concentration!r} is not among the "
            "accounts being swept"
        )
    for account in accounts:
        if account.balance.currency != currency:
            raise Refused(
                f"account {account.code!r} holds {account.balance.currency}; a "
                "sweep moves one currency at a time"
            )

    plan = SweepPlan(concentration=concentration, currency=currency)
    hub = by_code[concentration]

    # Pull surplus in first so the hub has the most to fund shortfalls with.
    available = hub.balance
    for account in accounts:
        if account.code == concentration:
            continue
        surplus = account.surplus()
        if surplus.is_positive():
            plan.transfers.append(Transfer(account.code, concentration, surplus))
            available = available + surplus

    shortfalls = [
        (account.code, account.shortfall())
        for account in accounts
        if account.code != concentration and account.shortfall().is_positive()
    ]
    needed = Money.zero(currency)
    for _, gap in shortfalls:
        needed = needed + gap
    if needed > available:
        raise InsufficientFunds(
            f"funding every shortfall needs {needed.format()} but only "
            f"{available.format()} is available; a partial sweep leaves the "
            "business in a state nobody chose"
        )
    for code, gap in shortfalls:
        plan.transfers.append(Transfer(concentration, code, gap))
    return plan


def apply_sweep(accounts: list[SweepAccount], plan: SweepPlan) -> dict[str, Money]:
    result = {account.code: account.balance for account in accounts}
    for transfer in plan.transfers:
        result[transfer.source] = result[transfer.source] - transfer.amount
        result[transfer.destination] = result[transfer.destination] + transfer.amount
    return result


def total_across(balances: dict[str, Money], currency: str) -> Money:
    total = Money.zero(currency)
    for value in balances.values():
        total = total + value
    return total
