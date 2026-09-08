"""Standard charts: the accounts a business needs, numbered the way people expect.

Every business builds roughly the same chart of accounts, and the
numbering convention is close to universal: assets in the one
thousands, liabilities in the two thousands, equity in the three
thousands, income in the four thousands, and expenses from five
thousand up. That convention is worth encoding because a chart that
follows it is legible to any accountant who picks it up, and one
that does not costs a day of translation on every handover. This
module builds standard charts for the shapes that recur, a simple
service business, a retailer that carries stock and therefore needs
cost of goods sold, and a payments business that needs clearing and
reserve accounts most templates lack. The builder validates as it
goes rather than at the end, so an account whose code falls outside
the range for its type is refused at the point it is added and the
mistake is attributable. Templates are a starting point rather than
a straitjacket, so the builder returns a normal chart that callers
extend, and the range check is available separately for the
accounts they add themselves.
"""

from __future__ import annotations

from mint.accounts import AccountType
from mint.chart import Chart
from mint.errors import Refused

RANGES: dict[AccountType, tuple[int, int]] = {
    AccountType.ASSET: (1000, 1999),
    AccountType.LIABILITY: (2000, 2999),
    AccountType.EQUITY: (3000, 3999),
    AccountType.INCOME: (4000, 4999),
    AccountType.EXPENSE: (5000, 9999),
}


def range_for(account_type: AccountType) -> tuple[int, int]:
    return RANGES[account_type]


def code_matches_type(code: str, account_type: AccountType) -> bool:
    if not code.isdigit():
        return False
    low, high = RANGES[account_type]
    return low <= int(code) <= high


def check_code(code: str, account_type: AccountType) -> None:
    if not code_matches_type(code, account_type):
        low, high = RANGES[account_type]
        raise Refused(
            f"code {code!r} is outside the {low} to {high} range that a "
            f"{account_type.value} account uses by convention; a chart that "
            "breaks the numbering costs a day of translation on every handover"
        )


def _build(chart: Chart, rows: list[tuple[str, str, AccountType]], currency: str) -> Chart:
    for code, name, account_type in rows:
        check_code(code, account_type)
        chart.add(code, name, account_type, currency)
    return chart


def service_business(currency: str = "USD") -> Chart:
    return _build(
        Chart(),
        [
            ("1000", "Cash", AccountType.ASSET),
            ("1200", "Accounts Receivable", AccountType.ASSET),
            ("1400", "Prepaid Expenses", AccountType.ASSET),
            ("2000", "Accounts Payable", AccountType.LIABILITY),
            ("2100", "Deferred Revenue", AccountType.LIABILITY),
            ("2200", "Accrued Expenses", AccountType.LIABILITY),
            ("3000", "Contributed Capital", AccountType.EQUITY),
            ("3900", "Retained Earnings", AccountType.EQUITY),
            ("4000", "Service Revenue", AccountType.INCOME),
            ("4900", "Refunds", AccountType.INCOME),
            ("5000", "Salaries", AccountType.EXPENSE),
            ("5100", "Rent", AccountType.EXPENSE),
            ("5200", "Software", AccountType.EXPENSE),
            ("5900", "Bad Debt", AccountType.EXPENSE),
        ],
        currency,
    )


def retailer(currency: str = "USD") -> Chart:
    chart = service_business(currency)
    for code, name, account_type in [
        ("1300", "Inventory", AccountType.ASSET),
        ("4100", "Product Sales", AccountType.INCOME),
        ("5300", "Cost of Goods Sold", AccountType.EXPENSE),
        ("5400", "Shrinkage", AccountType.EXPENSE),
    ]:
        check_code(code, account_type)
        chart.add(code, name, account_type, currency)
    return chart


def payments_business(currency: str = "USD") -> Chart:
    chart = service_business(currency)
    for code, name, account_type in [
        ("1100", "Clearing", AccountType.ASSET),
        ("1150", "Reserve Held", AccountType.ASSET),
        ("2300", "Merchant Payable", AccountType.LIABILITY),
        ("2400", "Customer Wallets", AccountType.LIABILITY),
        ("5500", "Processing Fees", AccountType.EXPENSE),
        ("5600", "Chargeback Losses", AccountType.EXPENSE),
    ]:
        check_code(code, account_type)
        chart.add(code, name, account_type, currency)
    return chart


def audit_codes(chart: Chart) -> list[str]:
    off_convention: list[str] = []
    for code in sorted(chart.accounts):
        account = chart.get(code)
        if not code_matches_type(code, account.type):
            off_convention.append(code)
    return off_convention
