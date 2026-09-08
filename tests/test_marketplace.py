from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.marketplace import SellerLine, split_payment, split_refund
from mint.money import Money


def _split():
    lines = [
        SellerLine("s1", Money.of(60, "USD"), Fraction(10, 100)),
        SellerLine("s2", Money.of(40, "USD"), Fraction(15, 100)),
    ]
    return split_payment(Money.of(100, "USD"), lines)


class TestSplit:
    def test_each_seller_keeps_its_line_less_commission(self):
        split = _split()
        assert split.seller("s1").commission == Money.of(6, "USD")
        assert split.seller("s1").net == Money.of(54, "USD")
        assert split.seller("s2").net == Money.of(34, "USD")

    def test_the_platform_takes_the_commissions(self):
        assert _split().platform == Money.of(12, "USD")

    def test_the_parts_sum_back_to_the_payment(self):
        assert _split().reconciles()

    def test_different_rates_per_seller_need_no_special_case(self):
        # 60 at 10% and 40 at 15% both come to 6.00, so the amounts alone
        # prove nothing; the effective rates are what differ.
        split = _split()
        first = split.seller("s1")
        second = split.seller("s2")
        assert Fraction(first.commission.units, first.gross.units) == Fraction(1, 10)
        assert Fraction(second.commission.units, second.gross.units) == Fraction(15, 100)


class TestRefunds:
    def test_a_refund_claws_back_proportional_commission(self):
        split = _split()
        back = split_refund(split, "s1", Money.of(30, "USD"))
        assert back.commission == Money.of(3, "USD")
        assert back.net == Money.of(27, "USD")

    def test_a_full_refund_returns_the_whole_commission(self):
        split = _split()
        back = split_refund(split, "s1", Money.of(60, "USD"))
        assert back.commission == split.seller("s1").commission

    def test_refunding_more_than_sold_is_refused(self):
        with pytest.raises(Refused):
            split_refund(_split(), "s1", Money.of(100, "USD"))


class TestRefusals:
    def test_lines_that_do_not_total_the_payment_are_refused(self):
        with pytest.raises(Refused) as caught:
            split_payment(
                Money.of(100, "USD"),
                [SellerLine("s1", Money.of(60, "USD"), Fraction(1, 10))],
            )
        assert "whole payment" in str(caught.value)

    def test_an_empty_split_is_refused(self):
        with pytest.raises(Refused):
            split_payment(Money.of(100, "USD"), [])

    def test_a_full_commission_rate_is_refused(self):
        with pytest.raises(Refused):
            SellerLine("s1", Money.of(10, "USD"), Fraction(1))

    def test_an_unknown_seller_is_refused(self):
        with pytest.raises(Refused):
            _split().seller("nobody")
