from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.paymentfile import PaymentFile, verify

DAY = datetime.date(2026, 6, 1)


def _file() -> PaymentFile:
    payment_file = PaymentFile("F-1", "USD", DAY, "1000")
    payment_file.add("P-1", "Acme Ltd", "GB82WEST12345698765432", Money.of(500, "USD"))
    payment_file.add("P-2", "Beta Inc", "GB82WEST12345698765432", Money.of(250, "USD"))
    return payment_file


class TestBuilding:
    def test_the_control_totals_are_computed(self):
        payment_file = _file()
        assert payment_file.count() == 2
        assert payment_file.control_total() == Money.of(750, "USD")

    def test_the_file_has_a_header_body_and_trailer(self):
        lines = _file().render()
        assert lines[0].startswith("HDR|")
        assert lines[1].startswith("PMT|")
        assert lines[-1] == "TRL|2|75000"

    def test_a_duplicate_reference_is_refused(self):
        payment_file = _file()
        with pytest.raises(Refused) as caught:
            payment_file.add("P-1", "Acme", "GB82", Money.of(1, "USD"))
        assert "may pay twice" in str(caught.value)

    def test_an_empty_file_is_refused(self):
        with pytest.raises(Refused) as caught:
            PaymentFile("F-2", "USD", DAY, "1000").render()
        assert "upstream failure" in str(caught.value)

    def test_a_wrong_currency_instruction_is_refused(self):
        with pytest.raises(Refused):
            _file().add("P-3", "Gamma", "GB82", Money.of(1, "EUR"))


class TestVerification:
    def test_an_intact_file_verifies(self):
        result = verify(_file().to_text())
        assert result.is_intact()
        assert result.problem() is None

    def test_a_lost_line_fails_the_count(self):
        lines = _file().render()
        del lines[1]
        result = verify("\n".join(lines))
        assert not result.count_matches()
        assert "a line was lost or added" in result.problem()

    def test_a_tampered_amount_fails_the_sum(self):
        lines = _file().render()
        lines[1] = lines[1].replace("|50000", "|90000")
        result = verify("\n".join(lines))
        assert result.count_matches()
        assert not result.total_matches()
        assert "an amount was altered" in result.problem()

    def test_an_added_line_fails_too(self):
        lines = _file().render()
        lines.insert(2, "PMT|P-9|Ghost|GB82|10000")
        result = verify("\n".join(lines))
        assert not result.is_intact()

    def test_the_file_id_survives_verification(self):
        assert verify(_file().to_text()).file_id == "F-1"


class TestMalformed:
    def test_a_missing_header_is_refused(self):
        with pytest.raises(Refused):
            verify("PMT|P-1|Acme|GB82|100\nTRL|1|100")

    def test_a_missing_trailer_is_refused(self):
        with pytest.raises(Refused):
            verify("HDR|F-1|2026-06-01|1000|USD\nPMT|P-1|Acme|GB82|100")

    def test_a_junk_body_record_is_refused(self):
        text = "HDR|F-1|2026-06-01|1000|USD\nJUNK|x\nTRL|1|100"
        with pytest.raises(Refused):
            verify(text)
