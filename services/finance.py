"""Finance-only invoice reads, integer-cent budgets and pending approvals."""

from database import one, rows, db, today
from services.common import (
    operation,
    require,
    role,
    self_access,
    actor,
    money,
    text,
    pending,
)


def budget(department_id):
    from services.common import department_id as resolve_department

    department_id = resolve_department(department_id)
    r = one("SELECT * FROM budgets WHERE department_id=?", (department_id,))
    require(r is not None, "Department budget not found.", "not_found")
    r["remaining_cents"] = (
        r["allocated_cents"] - r["committed_cents"] - r["spent_cents"]
    )
    return r


@operation("finance")
def get_invoice_status(invoice_id: str) -> dict:
    """Finance role retrieves an invoice payment status; monetary values are integer EGP cents."""
    role("finance")
    r = one("SELECT * FROM invoices WHERE id=?", (invoice_id,))
    require(r is not None, "Invoice not found.", "not_found")
    return r


@operation("finance")
def check_duplicate_invoice(vendor_id: str, invoice_number: str, amount: float) -> dict:
    """Finance compares vendor, invoice number and exact amount; flags number matches with amount discrepancies."""
    role("finance")
    vendor_id = text(vendor_id, "Vendor ID", 100)
    invoice_number = text(invoice_number, "Invoice number", 100)
    cents = money(amount)
    found = rows(
        "SELECT id,amount_cents FROM invoices WHERE vendor_id=? AND invoice_number=?",
        (vendor_id, invoice_number),
    )
    return {
        "possible_duplicate": bool(found),
        "exact_match": any(r["amount_cents"] == cents for r in found),
        "matches": found,
    }


@operation("finance")
def check_department_budget(department_id: str, amount: float) -> dict:
    """Finance or the department's manager compares positive EGP amount with remaining budget."""
    user = role("finance", "manager")
    from services.common import department_id as resolve_department

    department_id = resolve_department(department_id)
    cents = money(amount)
    if "finance" not in user["roles"]:
        require(
            one(
                "SELECT department_id FROM employees WHERE id=?", (user["employee_id"],)
            )["department_id"]
            == department_id,
            "Access denied to another department budget.",
            "forbidden",
        )
    b = budget(department_id)
    return {
        **b,
        "requested_cents": cents,
        "sufficient": cents <= b["remaining_cents"],
        "currency": "EGP",
    }


@operation("finance", write=True)
def request_expense_approval(employee_id: str, amount: float, description: str) -> dict:
    """Request own purchase approval against department budget; pending requests reserve budget, not payment."""
    p = self_access(employee_id)
    require(p["status"] == "active", "Employee must be active.")
    cents = money(amount)
    description = text(description, "Purchase description")
    b = budget(p["department_id"])
    payload = {
        "department_id": p["department_id"],
        "amount_cents": cents,
        "description": description,
    }
    import json

    found = one(
        "SELECT id,status FROM requests WHERE kind='purchase_approval' AND owner_id=? AND payload=? AND status IN ('pending','approved')",
        (employee_id, json.dumps(payload, sort_keys=True)),
    )
    if found:
        return {"request_id": found["id"], "status": found["status"], "existing": True}
    require(
        cents <= b["remaining_cents"], "Insufficient uncommitted department budget."
    )
    result = pending("purchase_approval", employee_id, payload)
    db().execute(
        "UPDATE budgets SET committed_cents=committed_cents+? WHERE department_id=?",
        (cents, p["department_id"]),
    )
    return {**result, "reserved_cents": cents, "payment_made": False}


@operation("finance")
def get_overdue_invoices() -> dict:
    """Finance lists unpaid invoices with due dates before company-local today."""
    role("finance")
    return {
        "invoices": rows(
            "SELECT * FROM invoices WHERE payment_status!='paid' AND due_date<? ORDER BY due_date",
            (str(today()),),
        )
    }
