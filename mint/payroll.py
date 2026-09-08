"""Payroll: gross to net, in the order the deductions legally have to happen.

A payslip is a sequence, not a subtraction, and the sequence is
legislated. Pre-tax deductions come out first and reduce taxable
pay, which is the whole point of a pre-tax benefit; income tax is
then computed on what remains; post-tax deductions come out of what
is left after tax. Doing these in the wrong order changes the tax,
so this module fixes the order and names each stage in the result,
which is also what a payslip must show an employee. Employer
contributions are tracked separately and never subtracted from net
pay, because they are a cost to the employer rather than a
deduction from the employee, and mixing the two is the mistake that
makes a payslip appear to take money the employee never had. Net
pay is refused if the deductions would take it below zero, since a
payslip that owes the employer money is a data error rather than a
payroll run, and the total cost of employment is reported as gross
plus employer contributions, which is the figure a budget needs and
a payslip never shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from mint.errors import Refused
from mint.money import Money
from mint.rounding import Rounding, scale
from mint.taxbracket import BracketTable


class DeductionKind(Enum):
    PRE_TAX = "pre_tax"
    POST_TAX = "post_tax"
    EMPLOYER = "employer"


@dataclass(frozen=True)
class Deduction:
    name: str
    kind: DeductionKind
    amount: Money | None = None
    rate: Fraction | None = None

    def __post_init__(self) -> None:
        if self.amount is None and self.rate is None:
            raise Refused(f"deduction {self.name!r} has neither an amount nor a rate")
        if self.rate is not None and (self.rate < 0 or self.rate >= 1):
            raise Refused(f"deduction {self.name!r} has a rate outside zero to one")
        if self.amount is not None and self.amount.is_negative():
            raise Refused(f"deduction {self.name!r} has a negative amount")

    def against(self, base: Money) -> Money:
        if self.amount is not None:
            return self.amount
        return scale(base, self.rate, Rounding.HALF_EVEN)


@dataclass(frozen=True)
class Payslip:
    gross: Money
    pre_tax: Money
    taxable: Money
    tax: Money
    post_tax: Money
    net: Money
    employer_cost: Money
    lines: tuple[tuple[str, int], ...]

    def total_cost(self) -> Money:
        return self.gross + self.employer_cost

    def reconciles(self) -> bool:
        return self.taxable - self.tax - self.post_tax == self.net


@dataclass
class PayrollRun:
    currency: str
    table: BracketTable
    deductions: list[Deduction] = field(default_factory=list)

    def add(self, deduction: Deduction) -> Deduction:
        self.deductions.append(deduction)
        return deduction

    def _of_kind(self, kind: DeductionKind) -> list[Deduction]:
        return [item for item in self.deductions if item.kind is kind]

    def compute(self, gross: Money) -> Payslip:
        if gross.currency != self.currency:
            raise Refused(
                f"this payroll runs in {self.currency}, not {gross.currency}"
            )
        if not gross.is_positive():
            raise Refused("a payslip starts from positive gross pay")
        zero = Money.zero(self.currency)
        lines: list[tuple[str, int]] = []

        pre_tax = zero
        for item in self._of_kind(DeductionKind.PRE_TAX):
            amount = item.against(gross)
            pre_tax = pre_tax + amount
            lines.append((item.name, -amount.units))
        if pre_tax > gross:
            raise Refused(
                "pre-tax deductions exceed gross pay; a payslip that owes the "
                "employer money is a data error, not a payroll run"
            )

        taxable = gross - pre_tax
        tax = self.table.tax_on(taxable).tax
        lines.append(("income tax", -tax.units))

        post_tax = zero
        for item in self._of_kind(DeductionKind.POST_TAX):
            amount = item.against(taxable)
            post_tax = post_tax + amount
            lines.append((item.name, -amount.units))

        net = taxable - tax - post_tax
        if net.is_negative():
            raise Refused(
                "deductions take net pay below zero; a payslip that owes the "
                "employer money is a data error, not a payroll run"
            )

        employer_cost = zero
        for item in self._of_kind(DeductionKind.EMPLOYER):
            amount = item.against(gross)
            employer_cost = employer_cost + amount

        return Payslip(
            gross=gross,
            pre_tax=pre_tax,
            taxable=taxable,
            tax=tax,
            post_tax=post_tax,
            net=net,
            employer_cost=employer_cost,
            lines=tuple(lines),
        )
