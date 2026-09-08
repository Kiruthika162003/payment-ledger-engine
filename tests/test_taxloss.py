from __future__ import annotations

from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.taxloss import LossPool, LossYear


def _pool(cap: Fraction = Fraction(1)) -> LossPool:
    pool = LossPool(currency="USD", shelter_cap=cap)
    pool.record_loss(2020, Money.of(100000, "USD"), expires_after=2025)
    pool.record_loss(2022, Money.of(50000, "USD"), expires_after=2030)
    return pool


class TestAvailability:
    def test_losses_accumulate(self):
        assert _pool().available(2023) == Money.of(150000, "USD")

    def test_a_loss_is_not_available_before_it_arose(self):
        assert _pool().available(2021) == Money.of(100000, "USD")

    def test_an_expired_loss_falls_out(self):
        assert _pool().available(2026) == Money.of(50000, "USD")


class TestUtilization:
    def test_the_oldest_loss_is_used_first(self):
        pool = _pool()
        pool.apply(2023, Money.of(60000, "USD"))
        assert pool.years[0].used == Money.of(60000, "USD")
        assert pool.years[1].used.is_zero()

    def test_profits_are_sheltered_to_zero_without_a_cap(self):
        pool = _pool()
        result = pool.apply(2023, Money.of(80000, "USD"))
        assert result.sheltered_everything()
        assert result.taxable_after.is_zero()

    def test_losses_run_out(self):
        pool = _pool()
        result = pool.apply(2023, Money.of(200000, "USD"))
        assert result.used == Money.of(150000, "USD")
        assert result.taxable_after == Money.of(50000, "USD")

    def test_a_loss_is_never_used_twice(self):
        pool = _pool()
        pool.apply(2023, Money.of(150000, "USD"))
        second = pool.apply(2024, Money.of(100000, "USD"))
        assert second.used.is_zero()
        assert pool.total_unused().is_zero()


class TestShelterCap:
    def test_a_cap_leaves_some_profit_taxable(self):
        pool = _pool(cap=Fraction(80, 100))
        result = pool.apply(2023, Money.of(100000, "USD"))
        assert result.shelterable == Money.of(80000, "USD")
        assert result.used == Money.of(80000, "USD")
        assert result.taxable_after == Money.of(20000, "USD")
        assert result.tax_due_despite_losses()

    def test_a_capped_year_leaves_losses_for_later(self):
        pool = _pool(cap=Fraction(80, 100))
        pool.apply(2023, Money.of(100000, "USD"))
        assert pool.available(2024) == Money.of(70000, "USD")


class TestExpiry:
    def test_expired_losses_are_reported_not_buried(self):
        pool = _pool()
        result = pool.apply(2026, Money.of(200000, "USD"))
        assert result.losses_expired == Money.of(100000, "USD")
        assert result.used == Money.of(50000, "USD")

    def test_the_pool_tracks_what_expired(self):
        pool = _pool()
        pool.apply(2026, Money.of(10, "USD"))
        assert pool.expired_total == Money.of(100000, "USD")


class TestRefusals:
    def test_a_duplicate_loss_year_is_refused(self):
        pool = _pool()
        with pytest.raises(Refused):
            pool.record_loss(2020, Money.of(10, "USD"), 2030)

    def test_a_loss_expiring_before_it_arose_is_refused(self):
        with pytest.raises(Refused):
            LossYear(2025, Money.of(10, "USD"), 2020)

    def test_applying_to_a_loss_is_refused(self):
        with pytest.raises(Refused) as caught:
            _pool().apply(2023, Money.of("-100.00", "USD"))
        assert "not another loss" in str(caught.value)

    def test_a_zero_cap_is_refused(self):
        with pytest.raises(Refused):
            LossPool(currency="USD", shelter_cap=Fraction(0))

    def test_a_wrong_currency_loss_is_refused(self):
        with pytest.raises(Refused):
            _pool().record_loss(2024, Money.of(10, "EUR"), 2030)
