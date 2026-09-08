from __future__ import annotations

import datetime

import pytest

from mint.errors import Refused
from mint.money import Money
from mint.statementimport import (
    SINGLE_COLUMN,
    TWO_COLUMN,
    ColumnMap,
    import_statement,
)

SINGLE = """Date,Description,Amount
2026-01-02,Customer payment,1500.00
2026-01-03,Rent,-800.00
2026-01-04,Refund,-25.50
"""

PAIRED = """Date,Narrative,Debit,Credit
2026-01-02,Customer payment,,1500.00
2026-01-03,Rent,800.00,
"""

MESSY = """Date,Description,Amount
2026-01-02,Good row,1500.00
not-a-date,Bad date,100.00
2026-01-04,Bad amount,abc
2026-01-05,Another good row,"2,000.00"
"""


class TestSingleColumn:
    def test_rows_import_with_their_signs(self):
        result = import_statement(SINGLE, SINGLE_COLUMN, "USD")
        assert result.is_clean()
        assert len(result.lines) == 3
        assert result.lines[0].amount == Money.of(1500, "USD")
        assert result.lines[1].amount == Money.of("-800.00", "USD")

    def test_credits_and_debits_are_separated(self):
        result = import_statement(SINGLE, SINGLE_COLUMN, "USD")
        assert len(result.credits()) == 1
        assert len(result.debits()) == 2

    def test_the_total_nets_the_statement(self):
        result = import_statement(SINGLE, SINGLE_COLUMN, "USD")
        assert result.total("USD") == Money.of("674.50", "USD")

    def test_a_bank_that_signs_the_other_way(self):
        mapping = ColumnMap(
            date="Date", description="Description", amount="Amount",
            debits_are_negative=False,
        )
        result = import_statement(SINGLE, mapping, "USD")
        assert result.lines[0].amount == Money.of("-1500.00", "USD")


class TestTwoColumn:
    def test_debit_and_credit_columns_are_read(self):
        result = import_statement(PAIRED, TWO_COLUMN, "USD")
        assert result.is_clean()
        assert result.lines[0].amount == Money.of(1500, "USD")
        assert result.lines[1].amount == Money.of("-800.00", "USD")

    def test_a_row_with_both_sides_is_a_problem(self):
        text = "Date,Narrative,Debit,Credit\n2026-01-02,Odd,10.00,20.00\n"
        result = import_statement(text, TWO_COLUMN, "USD")
        assert not result.is_clean()

    def test_a_row_with_neither_side_is_a_problem(self):
        text = "Date,Narrative,Debit,Credit\n2026-01-02,Empty,,\n"
        result = import_statement(text, TWO_COLUMN, "USD")
        assert len(result.problems) == 1


class TestProblems:
    def test_bad_rows_are_collected_not_fatal(self):
        result = import_statement(MESSY, SINGLE_COLUMN, "USD")
        assert len(result.lines) == 2
        assert len(result.problems) == 2

    def test_problems_carry_their_line_numbers(self):
        result = import_statement(MESSY, SINGLE_COLUMN, "USD")
        assert [problem.row for problem in result.problems] == [3, 4]

    def test_an_unreadable_amount_is_never_defaulted_to_zero(self):
        result = import_statement(MESSY, SINGLE_COLUMN, "USD")
        assert all(not line.amount.is_zero() for line in result.lines)

    def test_thousands_separators_are_tolerated(self):
        result = import_statement(MESSY, SINGLE_COLUMN, "USD")
        assert result.lines[-1].amount == Money.of(2000, "USD")

    def test_the_date_is_parsed(self):
        result = import_statement(SINGLE, SINGLE_COLUMN, "USD")
        assert result.lines[0].date == datetime.date(2026, 1, 2)


class TestMapping:
    def test_a_missing_column_is_refused_before_reading(self):
        with pytest.raises(Refused) as caught:
            import_statement("Date,Description\n", SINGLE_COLUMN, "USD")
        assert "different export" in str(caught.value)

    def test_a_map_with_both_styles_is_refused(self):
        with pytest.raises(Refused):
            ColumnMap(
                date="Date", description="D", amount="Amount",
                debit="Debit", credit="Credit",
            )

    def test_a_map_with_neither_style_is_refused(self):
        with pytest.raises(Refused):
            ColumnMap(date="Date", description="D")

    def test_a_custom_date_format(self):
        text = "Date,Description,Amount\n02/01/2026,Payment,10.00\n"
        mapping = ColumnMap(
            date="Date", description="Description", amount="Amount",
            date_format="%d/%m/%Y",
        )
        result = import_statement(text, mapping, "USD")
        assert result.lines[0].date == datetime.date(2026, 1, 2)
