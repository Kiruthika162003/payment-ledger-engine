from __future__ import annotations

import math

import pytest

from mint.benford import analyze, expected_share, leading_digit
from mint.errors import Refused
from mint.money import Money


def _benford_like(count: int = 900) -> list[Money]:
    # Build a sample whose leading digits follow the expected shares.
    amounts: list[Money] = []
    for digit in range(1, 10):
        share = expected_share(digit)
        for index in range(round(share * count)):
            amounts.append(Money.from_minor(int(f"{digit}{index % 90:02d}"), "USD"))
    return amounts


def _uniform(count: int = 900) -> list[Money]:
    amounts: list[Money] = []
    for index in range(count):
        digit = index % 9 + 1
        amounts.append(Money.from_minor(int(f"{digit}{index % 90:02d}"), "USD"))
    return amounts


class TestExpected:
    def test_one_leads_about_thirty_percent_of_the_time(self):
        assert abs(expected_share(1) - 0.301) < 0.001

    def test_nine_leads_under_five_percent(self):
        assert expected_share(9) < 0.05

    def test_the_shares_sum_to_one(self):
        assert abs(sum(expected_share(d) for d in range(1, 10)) - 1.0) < 1e-9

    def test_an_out_of_range_digit_is_refused(self):
        with pytest.raises(Refused):
            expected_share(0)


class TestLeadingDigit:
    def test_it_reads_the_first_digit_of_the_magnitude(self):
        assert leading_digit(4567) == 4

    def test_a_refund_is_taken_by_absolute_value(self):
        assert leading_digit(-8123) == 8

    def test_zero_has_no_leading_digit(self):
        assert leading_digit(0) is None


class TestAnalysis:
    def test_a_conforming_sample_reads_as_close(self):
        report = analyze(_benford_like())
        assert report.mean_absolute_deviation() < 0.006
        assert "close conformity" in report.verdict()

    def test_a_uniform_sample_is_flagged_as_nonconforming(self):
        report = analyze(_uniform())
        assert report.mean_absolute_deviation() > 0.015
        assert "reason to look" in report.verdict()

    def test_the_verdict_never_claims_proof(self):
        report = analyze(_uniform())
        assert "evidence of anything" in report.verdict()

    def test_the_largest_deviation_is_named(self):
        report = analyze(_uniform())
        digit, deviation = report.largest_deviation()
        assert 1 <= digit <= 9
        assert not math.isnan(deviation)

    def test_zeros_are_excluded_from_the_sample(self):
        amounts = [*_benford_like(), *[Money.zero("USD")] * 50]
        report = analyze(amounts)
        assert report.sample_size == len(_benford_like())


class TestSampleSize:
    def test_a_small_sample_is_refused(self):
        with pytest.raises(Refused) as caught:
            analyze([Money.of(10, "USD")] * 20)
        assert "false confidence" in str(caught.value)

    def test_the_minimum_can_be_lowered_deliberately(self):
        report = analyze([Money.from_minor(123, "USD")] * 5, minimum=5)
        assert report.sample_size == 5
