"""A payables run: three-way match, approval, early-payment discount, and the file to the bank.

This example walks the accounts payable cycle a controller actually
performs. A purchase order is raised and partly received, an
invoice arrives and is matched against both, the bill is approved
by someone other than the person who entered it, the early-payment
discount is taken because the payment lands inside the window, and
the payment file is built with the control totals a bank checks
before it moves money. It composes the purchase order, the bill,
payment terms, duplicate detection, and the payment file, and every
printed line is pinned in the test suite.
"""

from __future__ import annotations

import datetime
from fractions import Fraction

from mint.bill import Bill
from mint.duplicate import PaymentRecord, scan
from mint.money import Money
from mint.paymentfile import PaymentFile, verify
from mint.purchaseorder import PurchaseOrder
from mint.terms import PaymentTerms

ISSUED = datetime.date(2026, 4, 1)
PAID = datetime.date(2026, 4, 8)


def _dollars(money: Money) -> str:
    return money.format(with_symbol=False)


def run() -> list[str]:
    lines = ["Payables run, April 2026"]

    order = PurchaseOrder("PO-2026-11", "USD")
    order.add_line("widget", 100, Money.of(5, "USD"))
    order.add_line("gadget", 20, Money.of(50, "USD"))
    lines.append(f"Ordered: {_dollars(order.ordered_total())}")

    order.receive("widget", 100)
    order.receive("gadget", 18)
    order.bill("widget", 100)
    order.bill("gadget", 20)
    findings = order.match()
    lines.append(f"Three-way match findings: {len(findings)}")
    for finding in findings:
        lines.append(f"  {finding.comparison} on {finding.sku}")
    lines.append(f"Payable as matched: {order.is_payable()}")

    order.receive("gadget", 2)
    lines.append(f"After the balance arrived, payable: {order.is_payable()}")

    terms = PaymentTerms(
        net_days=30, discount_percent=Fraction(2, 100), discount_days=10
    )
    bill = Bill("BILL-77", "Acme Supplies", Money.of(1500, "USD"), ISSUED, terms)
    lines.append(f"Bill terms: {terms.label()}")
    lines.append(f"Due: {bill.due_date().isoformat()}")

    bill.approve("controller")
    lines.append(f"Approved by: {bill.approved_by}")

    due = terms.amount_due(bill.amount, ISSUED, PAID)
    lines.append(f"Paid on {PAID.isoformat()}, discount taken: {_dollars(due)}")
    bill.pay(due, PAID, "wire-4412")
    lines.append(f"Outstanding after payment: {_dollars(bill.outstanding())}")

    payments = [
        PaymentRecord("p1", "Acme Supplies", due, PAID, "BILL-77"),
        PaymentRecord("p2", "Acme Supplies", due, PAID, "BILL 000077"),
    ]
    suspects = scan(payments)
    lines.append(f"Duplicate candidates: {len(suspects)}")
    lines.append(f"Strongest signals: {len(suspects[0].signals)}")

    payment_file = PaymentFile("F-2026-04", "USD", PAID, "1000")
    payment_file.add("P-1", "Acme Supplies", "GB82WEST12345698765432", due)
    payment_file.add("P-2", "Beta Services", "GB82WEST12345698765432", Money.of(400, "USD"))
    lines.append(f"File control total: {_dollars(payment_file.control_total())}")

    text = payment_file.to_text()
    lines.append(f"File verifies: {verify(text).is_intact()}")
    damaged = "\n".join(
        line for line in text.splitlines() if not line.startswith("PMT|P-2")
    )
    lines.append(f"After losing a line, verifies: {verify(damaged).is_intact()}")
    return lines


def main() -> None:
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
