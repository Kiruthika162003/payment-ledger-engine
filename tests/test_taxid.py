from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.taxid import Verdict, check, known_countries, normalize


class TestNormalization:
    def test_spaces_and_case_are_stripped(self):
        assert normalize("gb 123 4567 89") == "GB123456789"

    def test_punctuation_is_dropped(self):
        assert normalize("12-3456789") == "123456789"


class TestUnitedKingdom:
    def test_a_well_formed_number_passes(self):
        # 123456782 satisfies the modulus 97 rule.
        assert check("GB123456782", "GB").is_valid()

    def test_a_bad_check_digit_fails(self):
        result = check("GB123456789", "GB")
        assert result.verdict is Verdict.INVALID
        assert "check digits" in result.reason

    def test_the_wrong_length_fails(self):
        result = check("GB12345", "GB")
        assert "9 or 12 digits" in result.reason

    def test_the_country_prefix_is_optional(self):
        assert check("123456782", "GB").is_valid()


class TestOtherCountries:
    def test_a_german_number_is_nine_digits(self):
        assert check("DE123456789", "DE").is_valid()

    def test_a_short_german_number_fails(self):
        assert check("DE1234", "DE").verdict is Verdict.INVALID

    def test_a_french_number_has_eleven_characters(self):
        assert check("FR12345678901", "FR").is_valid()

    def test_a_us_employer_number_passes(self):
        assert check("12-3456789", "US").is_valid()

    def test_an_unassigned_us_prefix_fails(self):
        result = check("07-1234567", "US")
        assert "not an assigned range" in result.reason


class TestUnknownCountry:
    def test_an_unknown_country_is_neither_valid_nor_invalid(self):
        result = check("123456", "ZZ")
        assert result.verdict is Verdict.UNKNOWN_COUNTRY
        assert not result.is_valid()
        assert not result.is_checkable()

    def test_the_reason_says_why(self):
        assert "no format rule" in check("123456", "ZZ").reason

    def test_the_known_countries_are_listed(self):
        assert "GB" in known_countries()
        assert "US" in known_countries()


class TestRefusals:
    def test_a_blank_identifier_is_refused(self):
        with pytest.raises(Refused):
            check("   ", "GB")

    def test_a_bad_country_code_is_refused(self):
        with pytest.raises(Refused):
            check("123456789", "GBR")

    def test_a_numeric_country_code_is_refused(self):
        with pytest.raises(Refused):
            check("123456789", "12")
