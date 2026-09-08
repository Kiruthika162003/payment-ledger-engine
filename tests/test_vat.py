from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.vat import VatLedger, VatRate, VatSchedule


def _ledger() -> VatLedger:
    return VatLedger(
        currency="USD",
        schedule=VatSchedule(standard=Fraction(20, 100), reduced=Fraction(5, 100)),
    )


class TestOutputAndInput:
    def test_a_sale_charges_output_tax(self):
        ledger = _ledger()
        entry = ledger.sale(Money.of(1000, "USD"))
        assert entry.tax == Money.of(200, "USD")
        assert ledger.output_tax() == Money.of(200, "USD")

    def test_a_purchase_reclaims_input_tax(self):
        ledger = _ledger()
        ledger.purchase(Money.of(500, "USD"))
        assert ledger.input_tax() == Money.of(100, "USD")

    def test_the_return_nets_the_two_sides(self):
        ledger = _ledger()
        ledger.sale(Money.of(1000, "USD"))
        ledger.purchase(Money.of(500, "USD"))
        assert ledger.net_due() == Money.of(100, "USD")
        assert not ledger.is_refund()

    def test_a_heavy_purchasing_month_is_owed_a_refund(self):
        ledger = _ledger()
        ledger.sale(Money.of(100, "USD"))
        ledger.purchase(Money.of(900, "USD"))
        assert ledger.is_refund()
        assert ledger.net_due() == Money.of("-160.00", "USD")


class TestBands:
    def test_the_reduced_band_charges_less(self):
        ledger = _ledger()
        entry = ledger.sale(Money.of(1000, "USD"), VatRate.REDUCED)
        assert entry.tax == Money.of(50, "USD")

    def test_zero_and_exempt_charge_nothing(self):
        ledger = _ledger()
        assert ledger.sale(Money.of(1000, "USD"), VatRate.ZERO).tax.is_zero()
        assert ledger.sale(Money.of(1000, "USD"), VatRate.EXEMPT).tax.is_zero()


class TestReverseCharge:
    def test_the_buyer_accounts_for_both_sides(self):
        ledger = _ledger()
        output, input_side = ledger.reverse_charge_purchase(Money.of(1000, "USD"))
        assert output.tax == input_side.tax == Money.of(200, "USD")
        assert ledger.net_due().is_zero()

    def test_it_still_appears_on_the_return(self):
        ledger = _ledger()
        ledger.reverse_charge_purchase(Money.of(1000, "USD"))
        assert ledger.output_tax() == Money.of(200, "USD")
        assert ledger.input_tax() == Money.of(200, "USD")

    def test_reverse_charge_stays_out_of_taxable_turnover(self):
        ledger = _ledger()
        ledger.sale(Money.of(400, "USD"))
        ledger.reverse_charge_purchase(Money.of(1000, "USD"))
        assert ledger.taxable_turnover() == Money.of(400, "USD")


class TestRefusals:
    def test_a_wrong_currency_entry_is_refused(self):
        with pytest.raises(Refused):
            _ledger().sale(Money.of(100, "EUR"))

    def test_a_nonpositive_net_is_refused(self):
        with pytest.raises(Refused):
            _ledger().sale(Money.zero("USD"))
