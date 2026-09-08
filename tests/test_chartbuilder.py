from __future__ import annotations

import pytest

from mint.accounts import AccountType
from mint.chartbuilder import (
    audit_codes,
    check_code,
    code_matches_type,
    payments_business,
    range_for,
    retailer,
    service_business,
)
from mint.errors import Refused


class TestRanges:
    def test_assets_live_in_the_one_thousands(self):
        assert range_for(AccountType.ASSET) == (1000, 1999)

    def test_a_code_in_range_matches(self):
        assert code_matches_type("1200", AccountType.ASSET)

    def test_a_code_out_of_range_does_not(self):
        assert not code_matches_type("4200", AccountType.ASSET)

    def test_a_non_numeric_code_does_not_match(self):
        assert not code_matches_type("CASH", AccountType.ASSET)

    def test_check_code_refuses_with_the_range(self):
        with pytest.raises(Refused) as caught:
            check_code("4200", AccountType.ASSET)
        assert "1000 to 1999" in str(caught.value)


class TestTemplates:
    def test_the_service_chart_has_the_usual_accounts(self):
        chart = service_business()
        assert chart.has("1000")
        assert chart.has("3900")
        assert chart.get("4000").type is AccountType.INCOME

    def test_the_retailer_adds_inventory_and_cogs(self):
        chart = retailer()
        assert chart.has("1300")
        assert chart.get("5300").name == "Cost of Goods Sold"

    def test_the_payments_chart_adds_clearing_and_reserve(self):
        chart = payments_business()
        assert chart.has("1100")
        assert chart.has("1150")
        assert chart.get("2400").type is AccountType.LIABILITY

    def test_a_template_takes_its_currency(self):
        chart = service_business("EUR")
        assert chart.get("1000").currency == "EUR"

    def test_every_template_follows_the_convention(self):
        for chart in (service_business(), retailer(), payments_business()):
            assert audit_codes(chart) == []


class TestExtension:
    def test_a_chart_can_be_extended(self):
        chart = service_business()
        chart.add("5700", "Travel", AccountType.EXPENSE, "USD")
        assert chart.has("5700")

    def test_an_off_convention_extension_is_visible_to_the_audit(self):
        chart = service_business()
        chart.add("7000", "Odd Asset", AccountType.ASSET, "USD")
        assert audit_codes(chart) == ["7000"]
