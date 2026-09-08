from __future__ import annotations

import pytest

from mint.accounts import Side
from mint.errors import Refused
from mint.money import Money
from mint.posting import credit, debit


class TestConstruction:
    def test_debit_builds_a_debit_posting(self):
        p = debit("1000", Money.of(10, "USD"))
        assert p.side is Side.DEBIT
        assert p.is_debit()

    def test_credit_builds_a_credit_posting(self):
        p = credit("4000", Money.of(10, "USD"))
        assert p.side is Side.CREDIT
        assert not p.is_debit()

    def test_a_negative_amount_is_refused_with_the_remedy(self):
        with pytest.raises(Refused) as caught:
            debit("1000", Money.of("-1.00", "USD"))
        assert "flip the side" in str(caught.value)

    def test_a_zero_posting_is_refused(self):
        with pytest.raises(Refused) as caught:
            debit("1000", Money.zero("USD"))
        assert "moves nothing" in str(caught.value)


class TestUnits:
    def test_a_debit_contributes_only_to_debit_units(self):
        p = debit("1000", Money.of(10, "USD"))
        assert p.debit_units() == 1000
        assert p.credit_units() == 0

    def test_a_credit_contributes_only_to_credit_units(self):
        p = credit("4000", Money.of(10, "USD"))
        assert p.credit_units() == 1000
        assert p.debit_units() == 0

    def test_currency_comes_from_the_amount(self):
        assert debit("1000", Money.of(1, "EUR")).currency == "EUR"


class TestSignedFor:
    def test_a_debit_grows_a_debit_normal_account(self):
        p = debit("1000", Money.of(10, "USD"))
        assert p.signed_for(debit_normal=True) == 1000

    def test_a_debit_shrinks_a_credit_normal_account(self):
        p = debit("2000", Money.of(10, "USD"))
        assert p.signed_for(debit_normal=False) == -1000

    def test_flip_swaps_the_side(self):
        assert debit("1000", Money.of(1, "USD")).flip().side is Side.CREDIT
