"""Value added tax: output less input, and the reverse charge that moves the duty.

VAT is not a sales tax with a different name. A sales tax is
collected once from the final consumer; VAT is charged at every
stage and each business reclaims the tax it paid on its own inputs,
so what a business remits is the tax it charged less the tax it was
charged. That difference, output tax minus input tax, is the whole
return, and a system that tracks only the tax collected overstates
what is owed by the entire input side. This module keeps the two
sides separate and nets them, reporting a payable when output
exceeds input and a refund when it does not, since a business in a
month of heavy purchasing genuinely is owed money and flooring the
return at zero would quietly donate it. The reverse charge is the
other rule worth encoding: on qualifying cross-border business
supplies the supplier charges nothing and the buyer accounts for
both sides of the tax themselves, which nets to zero for a buyer
who can fully reclaim but must still appear on the return, so this
module records both entries rather than skipping a transaction that
happens to net out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale


class VatRate(Enum):
    STANDARD = "standard"
    REDUCED = "reduced"
    ZERO = "zero"
    EXEMPT = "exempt"


@dataclass(frozen=True)
class VatSchedule:
    standard: Fraction
    reduced: Fraction

    def rate_for(self, band: VatRate) -> Fraction:
        if band is VatRate.STANDARD:
            return self.standard
        if band is VatRate.REDUCED:
            return self.reduced
        return Fraction(0)


@dataclass(frozen=True)
class VatEntry:
    net: Money
    band: VatRate
    tax: Money
    is_input: bool
    reverse_charge: bool = False


@dataclass
class VatLedger:
    currency: str
    schedule: VatSchedule
    entries: list[VatEntry] = field(default_factory=list)

    def _tax_on(self, net: Money, band: VatRate) -> Money:
        if net.currency != self.currency:
            raise Refused(
                f"this VAT ledger is in {self.currency}, not {net.currency}"
            )
        if not net.is_positive():
            raise Refused("a VAT entry is on a positive net amount")
        return scale(net, self.schedule.rate_for(band), Rounding.HALF_EVEN)

    def sale(self, net: Money, band: VatRate = VatRate.STANDARD) -> VatEntry:
        entry = VatEntry(net, band, self._tax_on(net, band), is_input=False)
        self.entries.append(entry)
        return entry

    def purchase(self, net: Money, band: VatRate = VatRate.STANDARD) -> VatEntry:
        entry = VatEntry(net, band, self._tax_on(net, band), is_input=True)
        self.entries.append(entry)
        return entry

    def reverse_charge_purchase(
        self, net: Money, band: VatRate = VatRate.STANDARD
    ) -> tuple[VatEntry, VatEntry]:
        # The buyer accounts for both sides: output tax as if they had sold
        # it to themselves, and input tax they may reclaim.
        tax = self._tax_on(net, band)
        output = VatEntry(net, band, tax, is_input=False, reverse_charge=True)
        input_side = VatEntry(net, band, tax, is_input=True, reverse_charge=True)
        self.entries.extend([output, input_side])
        return output, input_side

    def output_tax(self) -> Money:
        total = Money.zero(self.currency)
        for entry in self.entries:
            if not entry.is_input:
                total = total + entry.tax
        return total

    def input_tax(self) -> Money:
        total = Money.zero(self.currency)
        for entry in self.entries:
            if entry.is_input:
                total = total + entry.tax
        return total

    def net_due(self) -> Money:
        return self.output_tax() - self.input_tax()

    def is_refund(self) -> bool:
        return self.net_due().is_negative()

    def taxable_turnover(self) -> Money:
        total = Money.zero(self.currency)
        for entry in self.entries:
            if not entry.is_input and not entry.reverse_charge:
                total = total + entry.net
        return total
