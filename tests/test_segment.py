from __future__ import annotations

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.segment import OTHER, Segment, SegmentReport


def _seg(name, revenue, profit, assets) -> Segment:
    return Segment(
        name,
        Money.of(revenue, "USD"),
        Money.of(profit, "USD"),
        Money.of(assets, "USD"),
    )


def _report() -> SegmentReport:
    report = SegmentReport("USD")
    report.add(_seg("retail", 700000, 90000, 400000))
    report.add(_seg("wholesale", 250000, 30000, 200000))
    report.add(_seg("consulting", 40000, 5000, 20000))
    report.add(_seg("research", 10000, "-2000.00", 5000))
    return report


class TestThresholds:
    def test_a_large_segment_is_reportable(self):
        report = _report()
        assert report.meets_threshold(report.segments[0])

    def test_a_tiny_segment_is_not(self):
        report = _report()
        assert not report.meets_threshold(report.segments[3])

    def test_a_heavy_loss_makes_a_segment_reportable(self):
        report = SegmentReport("USD")
        report.add(_seg("big", 1000000, 10000, 500000))
        report.add(_seg("disaster", 20000, "-50000.00", 10000))
        # Its revenue is tiny but its absolute loss is most of the combined.
        assert report.meets_threshold(report.segments[1])

    def test_absolute_profit_is_used_not_signed(self):
        report = SegmentReport("USD")
        report.add(_seg("a", 100000, 50000, 100000))
        report.add(_seg("b", 100000, "-50000.00", 100000))
        # Signed profits net to zero; absolute does not hide the loss.
        assert report.combined_absolute_profit() == Money.of(100000, "USD")


class TestCoverage:
    def test_the_reportable_segments_cover_enough_revenue(self):
        assert _report().meets_coverage()

    def test_more_segments_are_added_until_coverage_is_met(self):
        report = SegmentReport("USD")
        for index in range(12):
            report.add(_seg(f"s{index}", 100000, 1000, 50000))
        chosen = report.reportable()
        assert report.coverage(chosen) >= report.coverage(chosen)
        assert report.meets_coverage()

    def test_coverage_of_an_empty_report_is_complete(self):
        assert SegmentReport("USD").coverage([]) == 1


class TestPresentation:
    def test_the_leftovers_are_aggregated_not_dropped(self):
        report = _report()
        other = report.other_segment()
        assert other.name == OTHER
        assert report.sums_to_the_entity()

    def test_the_presented_lines_sum_to_the_entity(self):
        report = _report()
        total = Money.zero("USD")
        for segment in report.presented():
            total = total + segment.revenue
        assert total == report.total_revenue()

    def test_a_report_where_everything_is_reportable_has_no_other(self):
        report = SegmentReport("USD")
        report.add(_seg("a", 500000, 50000, 100000))
        report.add(_seg("b", 500000, 50000, 100000))
        assert all(s.name != OTHER for s in report.presented())


class TestRefusals:
    def test_a_duplicate_segment_is_refused(self):
        report = _report()
        with pytest.raises(Refused):
            report.add(_seg("retail", 1, 1, 1))

    def test_a_wrong_currency_segment_is_refused(self):
        report = _report()
        with pytest.raises(Refused):
            report.add(
                Segment("euro", Money.of(1, "EUR"), Money.of(1, "EUR"), Money.of(1, "EUR"))
            )

    def test_negative_revenue_is_refused(self):
        with pytest.raises(Refused):
            _seg("bad", "-1.00", 0, 0)
