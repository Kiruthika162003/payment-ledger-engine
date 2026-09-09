from __future__ import annotations

from examples import (
    coffee_day,
    group_close,
    lending_desk,
    marketplace_day,
    month_end,
    payables_run,
)

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


MARKETPLACE_DAY = [
    "Marketplace, one day",
    "Buyer paid: 100.00 USD",
    "  baker nets 54.00 USD after 6.00 USD commission",
    "  florist nets 34.00 USD after 6.00 USD commission",
    "Platform commission: 12.00 USD",
    "Split reconciles: True",
    "Reserve withheld: 10.00 USD",
    "Paid out today: 90.00 USD",
    "Reserve releases on: 2026-11-30",
    "Refunded 30.00 USD to a buyer; commission clawed back 3.00 USD",
    "Retried capture posted once: True",
    "Payout to bank: 67.10 USD",
    "Net revenue: 70.00 USD",
    "Books balanced: True",
    "Reserve released later: 10.00 USD",
    "Reserve balance after: 0.00 USD",
]


class TestMonthEnd:
    def test_the_transcript_is_pinned(self):
        assert month_end.run() == MONTH_END

    def test_main_prints_every_line(self, capsys):
        month_end.main()
        out = capsys.readouterr().out.splitlines()
        assert out == MONTH_END


PAYABLES_RUN = [
    "Payables run, April 2026",
    "Ordered: 1500.00 USD",
    "Three-way match findings: 1",
    "  billed against received on gadget",
    "Payable as matched: False",
    "After the balance arrived, payable: True",
    "Bill terms: 2/10 net 30",
    "Due: 2026-05-01",
    "Approved by: controller",
    "Paid on 2026-04-08, discount taken: 1470.00 USD",
    "Outstanding after payment: 30.00 USD",
    "Duplicate candidates: 1",
    "Strongest signals: 4",
    "File control total: 1870.00 USD",
    "File verifies: True",
    "After losing a line, verifies: False",
]

LENDING_DESK = [
    "Lending desk",
    "Monthly payment: 966.64 USD",
    "Stressed payment: 1037.92 USD",
    "Verdict: affordable",
    "Level payment: 966.64 USD",
    "Total interest: 7998.43 USD",
    "Final balance: 0",
    "First payment interest: 25000",
    "Last payment interest: 481",
    "Drawn at month end: 0.00 USD",
    "Interest for January: 20.00 USD",
    "Leverage: leverage passes with headroom of 1/2",
    "Interest cover: interest cover passes with headroom of 1",
    "All covenants pass: True",
    "Tightest test: leverage",
]

GROUP_CLOSE = [
    "Group close",
    "Controlled subsidiaries: ['S']",
    "Minority share of the sub: 2/5",
    "Subsidiary balances in its own currency: True",
    "Translated assets: 1200.00 USD",
    "Translated revenue: 880.00 USD",
    "Translation adjustment: 120.00 USD",
    "Translated statements balance: True",
    "Intercompany reciprocal: True",
    "Eliminable: 100.00 USD",
    "Included: ['P', 'S']",
    "Excluded as not controlled: ['A']",
    "Group assets after elimination: 6100.00 USD",
    "Minority interest: 288.00 USD",
    "Parent equity: 3432.00 USD",
    "Consolidated sheet balances: True",
]


class TestMarketplaceDay:
    def test_the_transcript_is_pinned(self):
        assert marketplace_day.run() == MARKETPLACE_DAY

    def test_main_prints_every_line(self, capsys):
        marketplace_day.main()
        out = capsys.readouterr().out.splitlines()
        assert out == MARKETPLACE_DAY


class TestPayablesRun:
    def test_the_transcript_is_pinned(self):
        assert payables_run.run() == PAYABLES_RUN

    def test_main_prints_every_line(self, capsys):
        payables_run.main()
        out = capsys.readouterr().out.splitlines()
        assert out == PAYABLES_RUN


class TestLendingDesk:
    def test_the_transcript_is_pinned(self):
        assert lending_desk.run() == LENDING_DESK

    def test_main_prints_every_line(self, capsys):
        lending_desk.main()
        out = capsys.readouterr().out.splitlines()
        assert out == LENDING_DESK


class TestGroupClose:
    def test_the_transcript_is_pinned(self):
        assert group_close.run() == GROUP_CLOSE

    def test_main_prints_every_line(self, capsys):
        group_close.main()
        out = capsys.readouterr().out.splitlines()
        assert out == GROUP_CLOSE
