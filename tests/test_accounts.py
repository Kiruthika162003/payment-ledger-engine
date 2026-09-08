from __future__ import annotations

from mint.accounts import Account, AccountType, Side, decreases, increases


class TestNormalSide:
    def test_assets_grow_on_the_debit_side(self):
        cash = Account("1000", "Cash", AccountType.ASSET, "USD")
        assert cash.normal_side() is Side.DEBIT
        assert cash.is_debit_normal()

    def test_liabilities_grow_on_the_credit_side(self):
        payable = Account("2000", "Payable", AccountType.LIABILITY, "USD")
        assert payable.normal_side() is Side.CREDIT
        assert not payable.is_debit_normal()

    def test_income_grows_on_the_credit_side(self):
        sales = Account("4000", "Sales", AccountType.INCOME, "USD")
        assert increases(sales.type) is Side.CREDIT
        assert decreases(sales.type) is Side.DEBIT


class TestSignedBalance:
    def test_a_debit_normal_account_is_positive_when_debited(self):
        cash = Account("1000", "Cash", AccountType.ASSET, "USD")
        assert cash.signed_units(500, 200) == 300

    def test_a_credit_normal_account_is_positive_when_credited(self):
        loan = Account("2000", "Loan", AccountType.LIABILITY, "USD")
        assert loan.signed_units(200, 500) == 300

    def test_an_asset_gone_negative_is_an_overdraft(self):
        cash = Account("1000", "Cash", AccountType.ASSET, "USD")
        assert cash.signed_units(100, 400) == -300


class TestSide:
    def test_a_side_has_an_opposite(self):
        assert Side.DEBIT.opposite() is Side.CREDIT
        assert Side.CREDIT.opposite() is Side.DEBIT


class TestTemporary:
    def test_income_and_expense_are_temporary(self):
        assert Account("4000", "Sales", AccountType.INCOME, "USD").is_temporary()
        assert Account("5000", "Rent", AccountType.EXPENSE, "USD").is_temporary()

    def test_assets_are_permanent(self):
        assert not Account("1000", "Cash", AccountType.ASSET, "USD").is_temporary()
