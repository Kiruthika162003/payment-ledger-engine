from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.iban import build, check_digits, electronic_format, is_valid, remainder


class TestValidation:
    def test_a_known_good_iban_passes(self):
        assert is_valid("GB82 WEST 1234 5698 7654 32")

    def test_a_mistyped_digit_fails(self):
        assert not is_valid("GB82 WEST 1234 5698 7654 33")

    def test_a_valid_iban_leaves_remainder_one(self):
        assert remainder("GB82WEST12345698765432") == 1

    def test_electronic_format_strips_and_uppercases(self):
        assert electronic_format("gb82 west-1234") == "GB82WEST1234"


class TestCheckDigits:
    def test_check_digits_rebuild_a_known_iban(self):
        assert check_digits("GB", "WEST12345698765432") == "82"

    def test_build_produces_a_valid_iban(self):
        built = build("DE", "370400440532013000")
        assert is_valid(built)
        assert built.startswith("DE")


class TestLengths:
    def test_a_wrong_length_for_a_known_country_fails(self):
        # Checksum may pass but the German length is 22, not 21.
        assert not is_valid("GB82WEST1234569876543")

    def test_an_unknown_country_is_judged_by_checksum_alone(self):
        built = build("ZZ", "12345678")
        assert is_valid(built)


class TestRefusals:
    def test_a_too_short_value_is_refused(self):
        with pytest.raises(Refused):
            remainder("GB8")

    def test_a_bad_country_code_is_refused(self):
        with pytest.raises(Refused):
            check_digits("G1", "12345")
