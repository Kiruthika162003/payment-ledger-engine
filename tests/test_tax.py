from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.tax import TaxLine, apply_tax, extract_tax


class TestApply:
    def test_a_single_rate_adds_forward(self):
        result = apply_tax(Money.of(100, "USD"), [TaxLine("state", Fraction(8, 100))])
        assert result.total_tax == Money.of("8.00", "USD")
        assert result.gross == Money.of("108.00", "USD")
        assert result.reconciles()

    def test_two_flat_rates_each_apply_to_the_net(self):
        result = apply_tax(
            Money.of(100, "USD"),
            [TaxLine("state", Fraction(6, 100)), TaxLine("city", Fraction(2, 100))],
        )
        assert dict(result.taxes) == {"state": 600, "city": 200}
        assert result.total_tax == Money.of("8.00", "USD")

    def test_compound_tax_grows_the_base(self):
        result = apply_tax(
            Money.of(100, "USD"),
            [TaxLine("gst", Fraction(5, 100)), TaxLine("pst", Fraction(10, 100))],
            compound=True,
        )
        # pst applies to 105, not 100: 5.00 + 10.50 = 15.50.
        assert dict(result.taxes) == {"gst": 500, "pst": 1050}
        assert result.total_tax == Money.of("15.50", "USD")


class TestExtract:
    def test_backing_tax_out_divides_not_multiplies(self):
        result = extract_tax(Money.of(108, "USD"), Fraction(8, 100))
        assert result.net == Money.of(100, "USD")
        assert result.total_tax == Money.of("8.00", "USD")
        assert result.reconciles()

    def test_reconciliation_holds_for_awkward_rates(self):
        result = extract_tax(Money.of("215.75", "USD"), Fraction(825, 10000))
        assert result.reconciles()


class TestRefusals:
    def test_a_negative_rate_line_is_refused(self):
        with pytest.raises(Refused):
            TaxLine("bad", Fraction(-1, 100))

    def test_extracting_at_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            extract_tax(Money.of(108, "USD"), Fraction(-8, 100))
