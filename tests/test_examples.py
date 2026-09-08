from __future__ import annotations

from examples import coffee_day

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


class TestCoffeeDay:
    def test_the_transcript_is_pinned(self):
        assert coffee_day.run() == COFFEE_DAY

    def test_main_prints_every_line(self, capsys):
        coffee_day.main()
        out = capsys.readouterr().out.splitlines()
        assert out == COFFEE_DAY
