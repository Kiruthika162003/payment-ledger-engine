from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.withholding import certificate_lines, gross_up, withhold


class TestWithhold:
    def test_the_contractor_receives_the_net(self):
        result = withhold(Money.of(1000, "USD"), Fraction(20, 100))
        assert result.withheld == Money.of(200, "USD")
        assert result.net == Money.of(800, "USD")

    def test_the_pieces_reconcile_to_the_gross(self):
        result = withhold(Money.of("1234.56", "USD"), Fraction(1875, 10000))
        assert result.reconciles()

    def test_a_zero_rate_withholds_nothing(self):
        result = withhold(Money.of(1000, "USD"), Fraction(0))
        assert result.withheld.is_zero()
        assert result.net == Money.of(1000, "USD")


class TestGrossUp:
    def test_the_promised_net_actually_arrives(self):
        result = gross_up(Money.of(800, "USD"), Fraction(20, 100))
        assert result.net >= Money.of(800, "USD")
        assert result.gross == Money.of(1000, "USD")

    def test_an_awkward_rate_never_short_pays(self):
        for major in (1, 7, 99, 1234):
            target = Money.of(major, "USD")
            result = gross_up(target, Fraction(1, 3))
            assert result.net >= target
            assert result.reconciles()

    def test_a_nonpositive_target_is_refused(self):
        with pytest.raises(Refused):
            gross_up(Money.zero("USD"), Fraction(1, 10))


class TestRefusals:
    def test_a_rate_of_one_is_refused(self):
        with pytest.raises(Refused) as caught:
            withhold(Money.of(100, "USD"), Fraction(1))
        assert "nothing to pay" in str(caught.value)

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            withhold(Money.of(100, "USD"), Fraction(-1, 10))

    def test_a_nonpositive_payment_is_refused(self):
        with pytest.raises(Refused):
            withhold(Money.zero("USD"), Fraction(1, 10))


class TestCertificate:
    def test_the_certificate_lists_the_figures(self):
        lines = dict(certificate_lines(withhold(Money.of(1000, "USD"), Fraction(20, 100))))
        assert lines["gross"] == "1000.00 USD"
        assert lines["withheld"] == "200.00 USD"
        assert lines["rate"] == "20%"
