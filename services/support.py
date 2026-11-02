"""Payroll, HR cases and IT requests; no payments or account changes."""

import json
import re
from database import db, one, rows, policy, utcnow, today
from services.common import (
    operation,
    require,
    self_access,
    employee,
    actor,
    role,
    month_range,
    money,
    text,
    day,
    pending,
)


def ticket(kind, eid, description, category=None):
    description = text(description, "Description")
    existing = one(
        "SELECT id,status FROM tickets WHERE kind=? AND employee_id=? AND description=? AND category IS ? AND status IN ('open','escalated')",
        (kind, eid, description, category),
    )
    if existing:
        return {
            "ticket_id": existing["id"],
            "status": existing["status"],
            "existing": True,
        }
    cur = db().execute(
        "INSERT INTO tickets(kind,employee_id,description,category,created_at) VALUES (?,?,?,?,?)",
        (kind, eid, description, category, utcnow()),
    )
    return {"ticket_id": cur.lastrowid, "status": "open"}


@operation("payroll")
def get_payslip(employee_id: str, month: str) -> dict:
    """Verified self or payroll role reads fictional payslip data for YYYY-MM. Amounts in EGP."""
    self_access(employee_id, "payroll")
    month_range(month)
    r = one(
        "SELECT * FROM payslips WHERE employee_id=? AND month=?", (employee_id, month)
    )
    require(r is not None, "Payslip not found.", "not_found")
    return {
        "employee_id": employee_id,
        "month": month,
        "currency": "EGP",
        "gross_pay": r["gross_cents"] / 100,
        "deductions": r["deduction_cents"] / 100,
        "net_pay": (r["gross_cents"] - r["deduction_cents"]) / 100,
        "fictional": True,
    }


@operation("payroll", write=True)
def create_payroll_ticket(employee_id: str, issue_description: str) -> dict:
    """Create own confidential payroll issue ticket; content is not exposed through IT status lookup."""
    self_access(employee_id)
    return ticket("payroll", employee_id, issue_description)


@operation("payroll", write=True)
def submit_expense_request(
    employee_id: str, amount: float, category: str, receipt_reference: str
) -> dict:
    """Submit own positive EGP reimbursement with supported category and receipt reference; no payment."""
    p = self_access(employee_id)
    require(p["status"] == "active", "Employee must be active.")
    cents = money(amount)
    require(
        cents <= policy("expense_limit_cents"),
        "Expense exceeds demo reimbursement limit.",
    )
    require(category in policy("expense_categories"), "Unsupported expense category.")
    receipt = text(receipt_reference, "Receipt reference", 200)
    for r in rows(
        "SELECT payload FROM requests WHERE kind='reimbursement' AND owner_id=? AND status IN ('pending','approved')",
        (employee_id,),
    ):
        require(
            json.loads(r["payload"])["receipt_reference"] != receipt,
            "Receipt already submitted.",
            "conflict",
        )
    return pending(
        "reimbursement",
        employee_id,
        {
            "amount_cents": cents,
            "currency": "EGP",
            "category": category,
            "receipt_reference": receipt,
        },
    )


@operation("payroll", write=True)
def create_hr_case(employee_id: str, category: str, description: str) -> dict:
    """Create own restricted HR case; return its reference without disclosing case content."""
    self_access(employee_id)
    category = text(category, "Category", 100)
    result = ticket("hr_case", employee_id, description, category)
    return {
        "case_reference": result["ticket_id"],
        "status": result["status"],
        "visibility": "Authorized HR personnel only; no case-reading tool is exposed.",
    }


@operation("payroll")
def search_hr_policy(query: str) -> dict:
    """Search local HR policy titles/content using case-insensitive word matching; never invent policies."""
    role("employee", "hr", "manager", "payroll", "finance")
    query = text(query, "Search query", 200)
    words = set(re.findall(r"\w+", query.casefold())) - {
        "what",
        "is",
        "the",
        "our",
        "company",
        "policy",
        "s",
        "for",
        "a",
        "of",
    }
    require(
        bool(words),
        "Include a specific policy topic such as remote work or annual leave.",
    )
    found = [
        p
        for p in rows("SELECT * FROM policies")
        if any(w in (p["title"] + " " + p["content"]).casefold() for w in words)
    ]
    return {
        "policies": found,
        "message": "Matching policies." if found else "No matching policy found.",
    }


@operation("it", write=True)
def create_it_ticket(employee_id: str, issue_description: str) -> dict:
    """Create an IT support ticket for the selected employee; default priority normal."""
    self_access(employee_id)
    return ticket("it", employee_id, issue_description)


@operation("it")
def get_it_ticket_status(ticket_id: int) -> dict:
    """Read own IT ticket status only; cannot read payroll, HR or customer tickets."""
    require(ticket_id > 0, "Ticket ID must be positive.")
    r = one(
        "SELECT id,employee_id,status,priority FROM tickets WHERE id=? AND kind='it'",
        (ticket_id,),
    )
    require(r is not None, "IT ticket not found.", "not_found")
    self_access(r["employee_id"])
    return r


@operation("it", write=True)
def request_software_license(employee_id: str, software_name: str) -> dict:
    """Request supported software if an unassigned license is available; allocation requires human review."""
    p = self_access(employee_id)
    require(p["status"] == "active", "Employee must be active.")
    software = one(
        "SELECT * FROM software WHERE lower(name)=lower(?)", (software_name,)
    )
    require(software is not None, "Unsupported software.", "not_found")
    require(
        not one(
            "SELECT 1 FROM licenses WHERE employee_id=? AND software_name=?",
            (employee_id, software["name"]),
        ),
        "License already assigned.",
    )
    pending_requests = rows(
        "SELECT payload FROM requests WHERE kind='software_license' AND status='pending'"
    )
    count = sum(
        json.loads(r["payload"])["software_name"] == software["name"]
        for r in pending_requests
    )
    require(software["available"] > count, "No unreserved licenses available.")
    return pending("software_license", employee_id, {"software_name": software["name"]})


@operation("it", write=True)
def request_company_device(employee_id: str, device_type: str) -> dict:
    """Request a laptop or mouse from inventory, pending equipment approval."""
    p = self_access(employee_id)
    require(p["status"] == "active", "Employee must be active.")
    item_id = {
        "laptop": "LAPTOP",
        "laptops": "LAPTOP",
        "mouse": "MOUSE",
        "mice": "MOUSE",
    }.get(device_type.casefold())
    require(item_id is not None, "Supported device types: laptop, mouse.")
    require(
        not one(
            "SELECT 1 FROM assets WHERE employee_id=? AND item_id=?",
            (employee_id, item_id),
        ),
        "Employee already has this device type; IT must review a replacement.",
    )
    from services.inventory import check_item

    check_item(item_id, 1)
    return pending("device", employee_id, {"item_id": item_id, "quantity": 1})


@operation("it")
def check_device_warranty(asset_id: str) -> dict:
    """Verify device ownership and compare its warranty expiration to company-local today."""
    r = one("SELECT * FROM assets WHERE id=?", (asset_id,))
    require(r is not None, "Device not found.", "not_found")
    self_access(r["employee_id"])
    return {
        "asset_id": asset_id,
        "warranty_end_date": r["warranty_end"],
        "under_warranty": day(r["warranty_end"]) >= today(),
    }
