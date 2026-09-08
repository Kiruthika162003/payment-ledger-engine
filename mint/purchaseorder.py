"""Three-way match: the purchase order, what arrived, and what was billed.

The control that stops a company paying for goods it never ordered
or never received is the three-way match: the invoice is paid only
if it agrees with a purchase order that authorized the spend and a
receipt that confirms delivery. Each of the three can disagree with
the others in a different way and each disagreement means something
different, so this module reports which comparison failed rather
than a single pass or fail. Billed more than ordered is a supplier
overcharging or a duplicate invoice. Billed more than received is
being charged for goods still in transit or never sent. Received
more than ordered is an over-delivery that someone has to decide
whether to keep. A tolerance is allowed because real deliveries
come a few units light or a few cents dearer and blocking every
such invoice stops the business, but the tolerance is explicit and
per-comparison rather than a fudge buried in a comparison, so an
auditor can see exactly how much slack the control was given.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money


@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise Refused(f"line {self.sku!r} orders at least one unit")
        if self.unit_price.is_negative():
            raise Refused(f"line {self.sku!r} has a negative price")

    def extended(self) -> Money:
        return Money.from_minor(
            self.unit_price.units * self.quantity, self.unit_price.currency
        )


@dataclass(frozen=True)
class MatchFinding:
    comparison: str
    sku: str
    detail: str


@dataclass
class PurchaseOrder:
    id: str
    currency: str
    lines: list[OrderLine] = field(default_factory=list)
    received: dict[str, int] = field(default_factory=dict)
    billed: dict[str, int] = field(default_factory=dict)

    def add_line(self, sku: str, quantity: int, unit_price: Money) -> OrderLine:
        if unit_price.currency != self.currency:
            raise Refused(
                f"line {sku!r} is priced in {unit_price.currency}, not "
                f"the order currency {self.currency}"
            )
        if any(line.sku == sku for line in self.lines):
            raise Refused(f"line {sku!r} is already on order {self.id!r}")
        line = OrderLine(sku, quantity, unit_price)
        self.lines.append(line)
        return line

    def line_for(self, sku: str) -> OrderLine:
        for line in self.lines:
            if line.sku == sku:
                return line
        raise Refused(f"order {self.id!r} has no line for {sku!r}")

    def receive(self, sku: str, quantity: int) -> int:
        self.line_for(sku)
        if quantity < 1:
            raise Refused("a receipt records at least one unit")
        self.received[sku] = self.received.get(sku, 0) + quantity
        return self.received[sku]

    def bill(self, sku: str, quantity: int) -> int:
        self.line_for(sku)
        if quantity < 1:
            raise Refused("an invoice line covers at least one unit")
        self.billed[sku] = self.billed.get(sku, 0) + quantity
        return self.billed[sku]

    def ordered_total(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.extended()
        return total

    def match(self, tolerance: Fraction = Fraction(0)) -> list[MatchFinding]:
        if tolerance < 0 or tolerance >= 1:
            raise Refused("a match tolerance is a fraction below one")
        findings: list[MatchFinding] = []
        for line in self.lines:
            ordered = line.quantity
            received = self.received.get(line.sku, 0)
            billed = self.billed.get(line.sku, 0)
            allowed = ordered + int(ordered * tolerance)
            if billed > allowed:
                findings.append(
                    MatchFinding(
                        "billed against ordered",
                        line.sku,
                        f"billed {billed} against {ordered} ordered; a supplier "
                        "overcharge or a duplicate invoice",
                    )
                )
            if billed > received + int(received * tolerance):
                findings.append(
                    MatchFinding(
                        "billed against received",
                        line.sku,
                        f"billed {billed} but only {received} received; goods in "
                        "transit or never sent",
                    )
                )
            if received > allowed:
                findings.append(
                    MatchFinding(
                        "received against ordered",
                        line.sku,
                        f"received {received} against {ordered} ordered; an "
                        "over-delivery someone must decide to keep",
                    )
                )
        return findings

    def is_payable(self, tolerance: Fraction = Fraction(0)) -> bool:
        return not self.match(tolerance)

    def fully_received(self) -> bool:
        return all(
            self.received.get(line.sku, 0) >= line.quantity for line in self.lines
        )
