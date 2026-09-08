from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.pricebook import PriceBook, PriceEntry

JAN = datetime.date(2026, 1, 1)
JUL = datetime.date(2026, 7, 1)
MAR = datetime.date(2026, 3, 1)


def _book() -> PriceBook:
    book = PriceBook()
    book.add(PriceEntry("widget", Money.of(100, "USD"), JAN))
    book.add(PriceEntry("widget", Money.of(90, "EUR"), JAN))
    book.add(PriceEntry("widget", Money.of(85, "USD"), JAN, segment="wholesale"))
    book.add(PriceEntry("widget", Money.of(70, "USD"), JAN, customer_id="c1"))
    return book


class TestSpecificity:
    def test_the_list_price_applies_by_default(self):
        assert _book().price_for("widget", "USD", MAR) == Money.of(100, "USD")

    def test_a_segment_price_beats_the_list(self):
        assert _book().price_for(
            "widget", "USD", MAR, segment="wholesale"
        ) == Money.of(85, "USD")

    def test_a_customer_price_beats_the_segment(self):
        assert _book().price_for(
            "widget", "USD", MAR, customer_id="c1", segment="wholesale"
        ) == Money.of(70, "USD")

    def test_currency_selects_its_own_price(self):
        assert _book().price_for("widget", "EUR", MAR) == Money.of(90, "EUR")


class TestEffectiveDating:
    def test_a_price_starts_on_its_start_date(self):
        book = PriceBook()
        book.add(PriceEntry("w", Money.of(10, "USD"), JUL))
        assert book.has_price("w", "USD", JUL)
        assert not book.has_price("w", "USD", MAR)

    def test_the_end_is_exclusive_so_there_is_no_overlap(self):
        book = PriceBook()
        book.add(PriceEntry("w", Money.of(10, "USD"), JAN, ends=JUL))
        book.add(PriceEntry("w", Money.of(12, "USD"), JUL))
        # On the changeover day exactly one price is in force.
        assert len(book.candidates("w", "USD", JUL)) == 1
        assert book.price_for("w", "USD", JUL) == Money.of(12, "USD")

    def test_the_old_price_applies_the_day_before(self):
        book = PriceBook()
        book.add(PriceEntry("w", Money.of(10, "USD"), JAN, ends=JUL))
        book.add(PriceEntry("w", Money.of(12, "USD"), JUL))
        day_before = JUL - datetime.timedelta(days=1)
        assert book.price_for("w", "USD", day_before) == Money.of(10, "USD")


class TestRefusals:
    def test_a_missing_price_is_refused_not_free(self):
        with pytest.raises(Refused) as caught:
            _book().price_for("gadget", "USD", MAR)
        assert "worse than a failed one" in str(caught.value)

    def test_an_entry_ending_before_it_starts_is_refused(self):
        with pytest.raises(Refused):
            PriceEntry("w", Money.of(10, "USD"), JUL, ends=JAN)

    def test_an_entry_cannot_target_both_customer_and_segment(self):
        with pytest.raises(Refused):
            PriceEntry(
                "w", Money.of(10, "USD"), JAN, customer_id="c1", segment="wholesale"
            )

    def test_skus_are_listed(self):
        assert _book().skus() == ["widget"]
