from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.luhn import check_digit, checksum, complete, is_valid


class TestValidation:
    def test_a_known_good_number_passes(self):
        assert is_valid("4539578763621486")

    def test_a_single_digit_error_is_caught(self):
        assert not is_valid("4539578763621487")

    def test_spaces_and_dashes_are_tolerated(self):
        assert is_valid("4539 5787 6362 1486")
        assert is_valid("4539-5787-6362-1486")


class TestCheckDigit:
    def test_the_check_digit_completes_a_number(self):
        assert check_digit("453957876362148") == 6

    def test_complete_produces_a_valid_number(self):
        assert complete("453957876362148") == "4539578763621486"
        assert is_valid(complete("79927398713"))

    def test_the_checksum_of_a_valid_number_is_zero(self):
        assert checksum("4539578763621486") == 0


class TestRefusals:
    def test_letters_are_refused_not_skipped(self):
        with pytest.raises(Refused) as caught:
            is_valid("4539a5787")
        assert "non-digit" in str(caught.value)

    def test_an_empty_value_is_refused(self):
        with pytest.raises(Refused):
            checksum("")

    def test_a_transposition_is_caught(self):
        # Swapping two adjacent unequal digits breaks the check.
        assert not is_valid("4539578763621846")
