from __future__ import annotations

import datetime
from fractions import Fraction

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.terms import PaymentTerms, TermsKind

ISSUED = datetime.date(2026, 1, 10)


class TestNetTerms:
    def test_net_thirty_is_due_thirty_days_out(self):
        terms = PaymentTerms(net_days=30)
        assert terms.due_date(ISSUED) == datetime.date(2026, 2, 9)

    def test_the_label_reads_as_written(self):
        assert PaymentTerms(net_days=30).label() == "net 30"

    def test_overdue_counts_from_the_due_date(self):
        terms = PaymentTerms(net_days=30)
        assert terms.days_overdue(ISSUED, datetime.date(2026, 2, 19)) == 10
        assert terms.days_overdue(ISSUED, datetime.date(2026, 2, 1)) == 0


class TestEarlyDiscount:
    def test_two_ten_net_thirty_gives_two_percent_inside_ten_days(self):
        terms = PaymentTerms(net_days=30, discount_percent=Fraction(2, 100), discount_days=10)
        due = terms.amount_due(Money.of(1000, "USD"), ISSUED, datetime.date(2026, 1, 15))
        assert due == Money.of(980, "USD")

    def test_a_day_late_forfeits_the_discount(self):
        terms = PaymentTerms(net_days=30, discount_percent=Fraction(2, 100), discount_days=10)
        due = terms.amount_due(Money.of(1000, "USD"), ISSUED, datetime.date(2026, 1, 21))
        assert due == Money.of(1000, "USD")

    def test_the_discount_deadline_is_reported(self):
        terms = PaymentTerms(net_days=30, discount_percent=Fraction(2, 100), discount_days=10)
        assert terms.discount_deadline(ISSUED) == datetime.date(2026, 1, 20)

    def test_the_shorthand_label(self):
        terms = PaymentTerms(net_days=30, discount_percent=Fraction(2, 100), discount_days=10)
        assert terms.label() == "2/10 net 30"


class TestEndOfMonth:
    def test_the_clock_starts_at_month_end(self):
        terms = PaymentTerms(net_days=15, kind=TermsKind.END_OF_MONTH)
        assert terms.due_date(ISSUED) == datetime.date(2026, 2, 15)

    def test_invoices_across_a_month_fall_due_together(self):
        terms = PaymentTerms(net_days=15, kind=TermsKind.END_OF_MONTH)
        early = terms.due_date(datetime.date(2026, 1, 2))
        late = terms.due_date(datetime.date(2026, 1, 28))
        assert early == late


class TestRefusals:
    def test_a_discount_window_past_the_due_date_is_refused(self):
        with pytest.raises(Refused) as caught:
            PaymentTerms(net_days=10, discount_percent=Fraction(2, 100), discount_days=30)
        assert "outlasts the due date" in str(caught.value)

    def test_negative_days_are_refused(self):
        with pytest.raises(Refused):
            PaymentTerms(net_days=-1)

    def test_a_discount_of_one_or_more_is_refused(self):
        with pytest.raises(Refused):
            PaymentTerms(net_days=30, discount_percent=Fraction(1), discount_days=5)
