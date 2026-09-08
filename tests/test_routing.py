from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.routing import (
    check_digit,
    complete,
    federal_reserve_district,
    is_valid,
    weighted_sum,
)


class TestValidation:
    def test_a_known_good_routing_number_passes(self):
        assert is_valid("021000021")

    def test_a_mistyped_digit_fails(self):
        assert not is_valid("021000022")

    def test_the_weighted_sum_is_a_multiple_of_ten(self):
        assert weighted_sum("021000021") % 10 == 0


class TestCheckDigit:
    def test_the_check_digit_completes_the_number(self):
        assert check_digit("02100002") == 1

    def test_complete_produces_a_valid_number(self):
        assert complete("02100002") == "021000021"
        assert is_valid(complete("11100002"))


class TestDistrict:
    def test_the_leading_pair_names_the_district(self):
        assert federal_reserve_district("021000021") == 2

    def test_the_thrift_range_maps_back(self):
        assert federal_reserve_district("221000021") == 2

    def test_an_unassigned_prefix_is_refused(self):
        with pytest.raises(Refused) as caught:
            federal_reserve_district("991000021")
        assert "assigned routing ranges" in str(caught.value)


class TestRefusals:
    def test_a_wrong_length_is_refused_not_padded(self):
        with pytest.raises(Refused) as caught:
            weighted_sum("02100002")
        assert "different field entirely" in str(caught.value)

    def test_letters_are_refused(self):
        with pytest.raises(Refused):
            weighted_sum("02100002X")
