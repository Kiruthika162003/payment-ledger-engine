from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.overdraft import (
    OverdraftPolicy,
    PostingOrder,
    compare_orders,
    extended_fee_due,
    process_day,
    reordering_cost,
)


def _policy(**kwargs) -> OverdraftPolicy:
    base = {
        "item_fee": Money.of(35, "USD"),
        "daily_cap_items": 3,
        "de_minimis": Money.of(5, "USD"),
        "extended_fee": Money.of(15, "USD"),
        "extended_after_days": 5,
    }
    base.update(kwargs)
    return OverdraftPolicy(**base)


def _debits():
    return [
        Money.of(100, "USD"),
        Money.of(20, "USD"),
        Money.of(20, "USD"),
        Money.of(20, "USD"),
    ]


class TestOrdering:
    def test_largest_first_overdraws_sooner(self):
        result = process_day(
            Money.of(100, "USD"), _debits(), _policy(), PostingOrder.LARGEST_FIRST
        )
        assert result.fees_charged == 3

    def test_smallest_first_charges_fewer_fees(self):
        result = process_day(
            Money.of(100, "USD"), _debits(), _policy(), PostingOrder.SMALLEST_FIRST
        )
        assert result.fees_charged < 3

    def test_the_reordering_has_a_price(self):
        assert reordering_cost(Money.of(100, "USD"), _debits(), _policy()).is_positive()

    def test_both_orders_are_available_to_compare(self):
        results = compare_orders(Money.of(100, "USD"), _debits(), _policy())
        assert set(results) == set(PostingOrder)


class TestCaps:
    def test_the_daily_cap_limits_the_fees(self):
        many = [Money.of(50, "USD")] * 10
        result = process_day(Money.zero("USD"), many, _policy(daily_cap_items=2))
        assert result.fees_charged == 2

    def test_a_de_minimis_shortfall_is_not_charged(self):
        result = process_day(
            Money.of(100, "USD"), [Money.of("102.00", "USD")], _policy()
        )
        assert result.fees_charged == 0

    def test_a_real_shortfall_is_charged(self):
        result = process_day(
            Money.of(100, "USD"), [Money.of(200, "USD")], _policy()
        )
        assert result.fees_charged == 1
        assert result.fee_total == Money.of(35, "USD")

    def test_an_account_in_credit_is_never_charged(self):
        result = process_day(
            Money.of(1000, "USD"), _debits(), _policy()
        )
        assert result.fees_charged == 0
        assert result.closing_balance == Money.of(840, "USD")


class TestExtended:
    def test_no_extended_fee_before_the_threshold(self):
        assert extended_fee_due(3, _policy()).is_zero()

    def test_the_extended_fee_applies_once_past_it(self):
        assert extended_fee_due(5, _policy()) == Money.of(15, "USD")

    def test_it_does_not_compound_with_more_days(self):
        assert extended_fee_due(50, _policy()) == extended_fee_due(5, _policy())


class TestRefusals:
    def test_a_zero_cap_is_refused(self):
        with pytest.raises(Refused):
            _policy(daily_cap_items=0)

    def test_a_negative_fee_is_refused(self):
        with pytest.raises(Refused):
            _policy(item_fee=Money.of("-1.00", "USD"))

    def test_a_nonpositive_debit_is_refused(self):
        with pytest.raises(Refused):
            process_day(Money.of(100, "USD"), [Money.zero("USD")], _policy())
