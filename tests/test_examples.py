from __future__ import annotations

from examples import coffee_day, month_end

COFFEE_DAY = [
    "Coffee shop, day one",
    "Owner invests capital: 2000.00 USD",
    "Cash sale: 4.50 USD",
    "Cash sale: 3.75 USD",
    "Cash sale: 5.25 USD",
    "Supplies bought on credit: 40.00 USD",
    "Rent paid, cash now: 1513.50 USD",
    "Sales for the day: 13.50 USD",
    "Net income: -526.50 USD",
    "Closed; retained earnings: -526.50 USD",
    "Sales after close: 0.00 USD",
    "Books balanced: True",
]


MONTH_END = [
    "Month end, March 2026",
    "Billed on account: 9000.00 USD",
    "Collected in advance, deferred: 1200.00 USD",
    "Recognized this month: 100.00 USD",
    "Still deferred: 1100.00 USD",
    "Accrued expense: 2450.75 USD",
    "Revenue for March: 9100.00 USD",
    "Expenses for March: 2450.75 USD",
    "Net income: 6649.25 USD",
    "Trial balance columns equal: True",
    "Balance sheet balances: True",
    "Closed; retained earnings: 6649.25 USD",
    "Revenue after close: 0.00 USD",
    "Books balanced: True",
]


class TestCoffeeDay:
    def test_the_transcript_is_pinned(self):
        assert coffee_day.run() == COFFEE_DAY

    def test_main_prints_every_line(self, capsys):
        coffee_day.main()
        out = capsys.readouterr().out.splitlines()
        assert out == COFFEE_DAY


class TestMonthEnd:
    def test_the_transcript_is_pinned(self):
        assert month_end.run() == MONTH_END

    def test_main_prints_every_line(self, capsys):
        month_end.main()
        out = capsys.readouterr().out.splitlines()
        assert out == MONTH_END
