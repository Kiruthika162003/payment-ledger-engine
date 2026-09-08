"""Multilateral netting: turning a web of mutual debts into the fewest payments.

When several entities in a group owe each other, settling every
obligation separately moves far more money than the group actually
owes, and each transfer costs a fee and a day of float. Netting
collapses the web: compute each party's net position across all its
obligations, and then settle only those net positions. The saving
is real and large, and the property that makes it safe is that
every party's net position is unchanged by the collapse, which this
module checks rather than assumes. Bilateral netting only nets
pairs, so A owing B and B owing C still moves twice; multilateral
netting nets each party against the group as a whole, so a party
that owes as much as it is owed pays nothing at all. The settlement
instructions are produced by pairing debtors against creditors
greedily, which is not the provably minimal set in every case but
is close and, more importantly, is deterministic, so the same
obligations always produce the same instructions and two runs can
be compared.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class Obligation:
    debtor: str
    creditor: str
    amount: Money

    def __post_init__(self) -> None:
        if self.debtor == self.creditor:
            raise Refused("an entity cannot owe itself")
        if not self.amount.is_positive():
            raise Refused("an obligation is for a positive amount")


@dataclass(frozen=True)
class Instruction:
    payer: str
    payee: str
    amount: Money


@dataclass
class NettingCycle:
    currency: str
    obligations: list[Obligation] = field(default_factory=list)

    def add(self, debtor: str, creditor: str, amount: Money) -> Obligation:
        if amount.currency != self.currency:
            raise Refused(
                f"this cycle nets {self.currency}, not {amount.currency}"
            )
        obligation = Obligation(debtor, creditor, amount)
        self.obligations.append(obligation)
        return obligation

    def parties(self) -> list[str]:
        found: set[str] = set()
        for item in self.obligations:
            found.add(item.debtor)
            found.add(item.creditor)
        return sorted(found)

    def gross_total(self) -> Money:
        total = Money.zero(self.currency)
        for item in self.obligations:
            total = total + item.amount
        return total

    def net_positions(self) -> dict[str, Money]:
        positions = {party: Money.zero(self.currency) for party in self.parties()}
        for item in self.obligations:
            positions[item.debtor] = positions[item.debtor] - item.amount
            positions[item.creditor] = positions[item.creditor] + item.amount
        return positions

    def bilateral_total(self) -> Money:
        pairs: dict[tuple[str, str], int] = {}
        for item in self.obligations:
            key = tuple(sorted((item.debtor, item.creditor)))
            sign = 1 if item.debtor == key[0] else -1
            pairs[key] = pairs.get(key, 0) + sign * item.amount.units
        total = Money.zero(self.currency)
        for units in pairs.values():
            total = total + Money.from_minor(abs(units), self.currency)
        return total

    def instructions(self) -> list[Instruction]:
        positions = self.net_positions()
        owing = (
            (party, -value.units)
            for party, value in positions.items()
            if value.is_negative()
        )
        owed = (
            (party, value.units)
            for party, value in positions.items()
            if value.is_positive()
        )
        debtors = sorted(owing, key=lambda pair: (-pair[1], pair[0]))
        creditors = sorted(owed, key=lambda pair: (-pair[1], pair[0]))
        out: list[Instruction] = []
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            payer, owed = debtors[i]
            payee, due = creditors[j]
            amount = min(owed, due)
            out.append(Instruction(payer, payee, Money.from_minor(amount, self.currency)))
            owed -= amount
            due -= amount
            debtors[i] = (payer, owed)
            creditors[j] = (payee, due)
            if owed == 0:
                i += 1
            if due == 0:
                j += 1
        return out

    def netted_total(self) -> Money:
        total = Money.zero(self.currency)
        for instruction in self.instructions():
            total = total + instruction.amount
        return total

    def saving(self) -> Money:
        return self.gross_total() - self.netted_total()

    def positions_preserved(self) -> bool:
        # The collapse is only safe if every party ends where it started.
        expected = self.net_positions()
        actual = {party: Money.zero(self.currency) for party in self.parties()}
        for instruction in self.instructions():
            actual[instruction.payer] = actual[instruction.payer] - instruction.amount
            actual[instruction.payee] = actual[instruction.payee] + instruction.amount
        return expected == actual
