from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.payroll import Deduction, DeductionKind, PayrollRun
from mint.taxbracket import Bracket, BracketTable


def _table() -> BracketTable:
    return BracketTable(
        brackets=(
            Bracket(Money.zero("USD"), Fraction(10, 100)),
            Bracket(Money.of(3000, "USD"), Fraction(20, 100)),
        )
    )


def _run() -> PayrollRun:
    run = PayrollRun(currency="USD", table=_table())
    run.add(
        Deduction("pension", DeductionKind.PRE_TAX, rate=Fraction(5, 100))
    )
    run.add(Deduction("union dues", DeductionKind.POST_TAX, amount=Money.of(25, "USD")))
    run.add(
        Deduction("employer pension", DeductionKind.EMPLOYER, rate=Fraction(3, 100))
    )
    return run


class TestOrder:
    def test_pre_tax_deductions_reduce_taxable_pay(self):
        slip = _run().compute(Money.of(5000, "USD"))
        assert slip.pre_tax == Money.of(250, "USD")
        assert slip.taxable == Money.of(4750, "USD")

    def test_tax_is_computed_on_the_reduced_base(self):
        slip = _run().compute(Money.of(5000, "USD"))
        # 3000 at 10% = 300, then 1750 at 20% = 350, total 650.
        assert slip.tax == Money.of(650, "USD")

    def test_post_tax_deductions_come_out_after_tax(self):
        slip = _run().compute(Money.of(5000, "USD"))
        assert slip.post_tax == Money.of(25, "USD")
        assert slip.net == Money.of(4075, "USD")

    def test_the_payslip_reconciles(self):
        assert _run().compute(Money.of(5000, "USD")).reconciles()


class TestEmployerCost:
    def test_employer_contributions_do_not_reduce_net_pay(self):
        slip = _run().compute(Money.of(5000, "USD"))
        assert slip.employer_cost == Money.of(150, "USD")
        assert slip.net == Money.of(4075, "USD")

    def test_total_cost_is_gross_plus_employer(self):
        slip = _run().compute(Money.of(5000, "USD"))
        assert slip.total_cost() == Money.of(5150, "USD")


class TestLines:
    def test_every_deduction_appears_as_a_line(self):
        slip = _run().compute(Money.of(5000, "USD"))
        names = [name for name, _ in slip.lines]
        assert names == ["pension", "income tax", "union dues"]

    def test_lines_are_negative_amounts(self):
        slip = _run().compute(Money.of(5000, "USD"))
        assert all(units < 0 for _, units in slip.lines)


class TestRefusals:
    def test_deductions_below_zero_net_are_refused(self):
        run = PayrollRun(currency="USD", table=_table())
        run.add(Deduction("huge", DeductionKind.POST_TAX, amount=Money.of(9000, "USD")))
        with pytest.raises(Refused) as caught:
            run.compute(Money.of(1000, "USD"))
        assert "owes the employer money" in str(caught.value)

    def test_pre_tax_above_gross_is_refused(self):
        run = PayrollRun(currency="USD", table=_table())
        run.add(Deduction("huge", DeductionKind.PRE_TAX, amount=Money.of(9000, "USD")))
        with pytest.raises(Refused):
            run.compute(Money.of(1000, "USD"))

    def test_a_deduction_with_neither_amount_nor_rate_is_refused(self):
        with pytest.raises(Refused):
            Deduction("empty", DeductionKind.PRE_TAX)

    def test_a_wrong_currency_run_is_refused(self):
        with pytest.raises(Refused):
            _run().compute(Money.of(1000, "EUR"))

    def test_nonpositive_gross_is_refused(self):
        with pytest.raises(Refused):
            _run().compute(Money.zero("USD"))
