from __future__ import annotations

import pytest

from mint.contingency import (
    Contingency,
    ContingencyRegister,
    Estimate,
    Likelihood,
    Treatment,
)
from mint.errors import Refused
from mint.money import Money


def _estimate(low: str = "10000.00", high: str = "30000.00") -> Estimate:
    return Estimate(Money.of(low, "USD"), Money.of(high, "USD"))


def _item(**kwargs) -> Contingency:
    base = {
        "id": "C-1",
        "description": "supplier lawsuit",
        "likelihood": Likelihood.PROBABLE,
        "estimate": _estimate(),
    }
    base.update(kwargs)
    return Contingency(**base)


class TestTreatment:
    def test_a_probable_estimable_item_is_provided(self):
        assert _item().treatment() is Treatment.PROVIDE

    def test_a_possible_item_is_only_disclosed(self):
        assert _item(likelihood=Likelihood.POSSIBLE).treatment() is Treatment.DISCLOSE

    def test_a_remote_item_is_ignored(self):
        assert _item(likelihood=Likelihood.REMOTE).treatment() is Treatment.IGNORE

    def test_a_probable_but_inestimable_item_is_disclosed_not_guessed(self):
        item = _item(estimate=None)
        assert item.treatment() is Treatment.DISCLOSE

    def test_a_possible_item_provides_nothing(self):
        item = _item(likelihood=Likelihood.POSSIBLE)
        assert item.required_provision().is_zero()


class TestEstimates:
    def test_a_point_estimate_is_used_directly(self):
        estimate = _estimate("20000.00", "20000.00")
        amount, basis = estimate.best_estimate()
        assert amount == Money.of(20000, "USD")
        assert "single estimate" in basis

    def test_a_range_uses_the_midpoint_and_says_so(self):
        amount, basis = _estimate().best_estimate()
        assert amount == Money.of(20000, "USD")
        assert "midpoint" in basis

    def test_a_backward_range_is_refused(self):
        with pytest.raises(Refused):
            Estimate(Money.of(100, "USD"), Money.of(10, "USD"))

    def test_a_negative_estimate_is_refused(self):
        with pytest.raises(Refused):
            Estimate(Money.of("-1.00", "USD"), Money.of(10, "USD"))


class TestProvisioning:
    def test_the_movement_is_the_increment(self):
        item = _item()
        assert item.post() == Money.of(20000, "USD")
        assert item.post().is_zero()

    def test_reassessing_downward_releases_the_provision(self):
        item = _item()
        item.post()
        item.reassess(Likelihood.POSSIBLE)
        assert item.movement() == Money.of("-20000.00", "USD")

    def test_reassessing_upward_creates_one(self):
        item = _item(likelihood=Likelihood.POSSIBLE)
        item.post()
        item.reassess(Likelihood.PROBABLE)
        assert item.movement() == Money.of(20000, "USD")


class TestDisclosure:
    def test_a_provided_item_says_what_it_provided(self):
        note = _item().disclosure()
        assert "provided at" in note

    def test_a_possible_item_gives_the_range(self):
        note = _item(likelihood=Likelihood.POSSIBLE).disclosure()
        assert "between" in note

    def test_an_inestimable_item_says_so(self):
        note = _item(likelihood=Likelihood.POSSIBLE, estimate=None).disclosure()
        assert "no reliable estimate" in note

    def test_a_remote_item_says_nothing(self):
        assert _item(likelihood=Likelihood.REMOTE).disclosure() is None


class TestRegister:
    def _register(self) -> ContingencyRegister:
        register = ContingencyRegister("USD")
        register.add(_item())
        register.add(_item(id="C-2", likelihood=Likelihood.POSSIBLE))
        register.add(_item(id="C-3", likelihood=Likelihood.REMOTE))
        return register

    def test_only_probable_items_are_provided(self):
        assert self._register().total_provided() == Money.of(20000, "USD")

    def test_possible_items_are_listed_separately(self):
        assert len(self._register().disclosed_only()) == 1

    def test_the_notes_skip_the_remote(self):
        assert len(self._register().notes()) == 2

    def test_maximum_exposure_counts_the_high_ends(self):
        assert self._register().maximum_exposure() == Money.of(60000, "USD")

    def test_a_duplicate_item_is_refused(self):
        register = self._register()
        with pytest.raises(Refused):
            register.add(_item())

    def test_a_blank_description_is_refused(self):
        with pytest.raises(Refused):
            _item(description="   ")
