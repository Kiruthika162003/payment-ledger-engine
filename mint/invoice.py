"""Invoices: line items to a subtotal, then discount, then tax, then a total.

An invoice is the arithmetic of a sale written down in the order
that keeps it defensible: extend each line to quantity times unit
price, sum to a subtotal, take the discounts, then apply tax to
what is actually owed after the discount, and total. The order is
not cosmetic. Tax follows discount because a customer owes tax on
the price they pay, not the price before the coupon, and an invoice
that taxes the pre-discount subtotal overcharges tax on money the
customer never spent. Each line extends with a single rounding, so
a hundred units at a third of a cent is one honest rounding rather
than a hundred that drift, and the whole invoice lives in one
currency because an invoice mixing currencies is two invoices in a
trench coat. The invoice reports every intermediate figure,
subtotal, discount, taxable base, tax, and total, so the document
shows its work and a dispute lands on a specific line rather than a
final number no one can take apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from mint.discount import Discount, apply_discounts
from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale
from mint.tax import TaxLine, apply_tax


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: Fraction
    unit_price: Money

    def extended(self) -> Money:
        return scale(self.unit_price, self.quantity, Rounding.HALF_EVEN)


@dataclass
class Invoice:
    currency: str
    lines: list[LineItem] = field(default_factory=list)
    discounts: list[Discount] = field(default_factory=list)
    taxes: list[TaxLine] = field(default_factory=list)

    def add_line(
        self, description: str, quantity: Fraction | int, unit_price: Money
    ) -> LineItem:
        if unit_price.currency != self.currency:
            raise Refused(
                f"line {description!r} is priced in {unit_price.currency}, not "
                f"the invoice currency {self.currency}"
            )
        if Fraction(quantity) <= 0:
            raise Refused(f"line {description!r} needs a positive quantity")
        item = LineItem(description, Fraction(quantity), unit_price)
        self.lines.append(item)
        return item

    def subtotal(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.extended()
        return total

    def taxable_base(self) -> Money:
        return apply_discounts(self.subtotal(), self.discounts).final

    def total(self) -> Money:
        return apply_tax(self.taxable_base(), self.taxes).gross

    def summary(self) -> dict[str, Money]:
        subtotal = self.subtotal()
        discounted = apply_discounts(subtotal, self.discounts)
        taxed = apply_tax(discounted.final, self.taxes)
        return {
            "subtotal": subtotal,
            "discount": discounted.total_discount(),
            "taxable": discounted.final,
            "tax": taxed.total_tax,
            "total": taxed.gross,
        }
