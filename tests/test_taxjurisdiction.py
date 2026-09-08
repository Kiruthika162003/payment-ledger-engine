from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.taxjurisdiction import Jurisdiction, TaxAddress


def _address() -> TaxAddress:
    address = TaxAddress("123 Main St")
    address.add(Jurisdiction("state", "state", Fraction(6, 100)))
    address.add(Jurisdiction("county", "county", Fraction(1, 100)))
    address.add(Jurisdiction("city", "city", Fraction(5, 1000)))
    return address


class TestCombinedRate:
    def test_rates_stack_additively(self):
        assert _address().combined_rate() == Fraction(75, 1000)

    def test_the_tax_is_one_rounding_on_the_combined_rate(self):
        assert _address().tax_on(Money.of(100, "USD")) == Money.of("7.50", "USD")

    def test_an_awkward_base_rounds_once(self):
        # 19.99 at 7.5% is 1.49925, which rounds to 1.50 as a single step.
        assert _address().tax_on(Money.of("19.99", "USD")) == Money.of("1.50", "USD")


class TestBreakdown:
    def test_the_breakdown_names_every_jurisdiction(self):
        parts = dict(_address().breakdown(Money.of(100, "USD")))
        assert set(parts) == {"state", "county", "city"}

    def test_the_parts_sum_to_the_tax_collected(self):
        address = _address()
        assert address.breakdown_reconciles(Money.of("19.99", "USD"))

    def test_the_split_follows_the_rates(self):
        parts = dict(_address().breakdown(Money.of(100, "USD")))
        assert parts["state"] == Money.of(6, "USD")
        assert parts["county"] == Money.of(1, "USD")
        assert parts["city"] == Money.of("0.50", "USD")


class TestExemption:
    def test_an_exempt_jurisdiction_leaves_the_rate(self):
        address = _address()
        address.exempt_from("city")
        assert address.combined_rate() == Fraction(7, 100)

    def test_an_exempt_jurisdiction_leaves_the_breakdown(self):
        address = _address()
        address.exempt_from("city")
        assert "city" not in dict(address.breakdown(Money.of(100, "USD")))

    def test_exempting_an_unknown_jurisdiction_is_refused(self):
        with pytest.raises(Refused):
            _address().exempt_from("moon")


class TestRefusals:
    def test_a_duplicate_jurisdiction_is_refused(self):
        address = _address()
        with pytest.raises(Refused):
            address.add(Jurisdiction("state", "state", Fraction(1, 100)))

    def test_a_negative_rate_is_refused(self):
        with pytest.raises(Refused):
            Jurisdiction("bad", "state", Fraction(-1, 100))

    def test_an_all_exempt_address_charges_nothing(self):
        address = _address()
        for name in ("state", "county", "city"):
            address.exempt_from(name)
        assert address.tax_on(Money.of(100, "USD")).is_zero()
        assert address.breakdown(Money.of(100, "USD")) == []
