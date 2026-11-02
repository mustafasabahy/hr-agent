"""Public directory, restricted profiles and pending employee workflows."""

import json
import re
from datetime import timedelta
from database import db, one, rows, policy, today
from services.common import (
    operation,
    require,
    role,
    self_access,
    employee,
    day,
    text,
    pending,
)


def public_person(person):
    return {k: person[k] for k in ["employee_id", "name", "department", "role"]}


@operation("employees")
def get_employee(name: str) -> dict:
    """Find a fictional employee by exact name, ignoring case and surrounding spaces."""
    role("employee", "hr", "manager", "finance", "payroll")
    name = text(name, "Employee name", 100)
    # Python casefold preserves compatibility for Unicode names.
    candidates = [
        person
        for person in rows(
            "SELECT e.id employee_id,e.name,d.name department,e.role FROM employees e JOIN departments d ON d.id=e.department_id"
        )
        if person["name"].casefold() == name.casefold()
    ]
    from services.common import BusinessError

    if len(candidates) > 1:
        raise BusinessError(
            "Multiple employees match this name. Ask for the department and stable employee ID; do not select an arbitrary match.",
            "ambiguous_employee",
        )
    if candidates:
        return public_person(candidates[0])
    raise BusinessError(f"Employee '{name}' was not found.", "not_found")


@operation("employees", write=True)
def update_employee_profile(employee_id: str, field: str, value: str) -> dict:
    """Update own phone or preferred_name only. Salary, role, identity and permissions cannot be changed."""
    p = self_access(employee_id)
    require(
        field in ["phone", "preferred_name"],
        "Only phone and preferred_name may be updated.",
    )
    value = text(value, "Profile value", 100)
    if field == "phone":
        require(
            bool(re.fullmatch(r"\+?[0-9 ()-]{7,25}", value)), "Invalid phone format."
        )
    require(p[field] != value, "Profile value is unchanged.", "conflict")
    # field is checked against a fixed allowlist above.
    db().execute(f"UPDATE employees SET {field}=? WHERE id=?", (value, employee_id))
    return {
        "employee_id": employee_id,
        "field": field,
        "old_value": p[field],
        "new_value": value,
    }


@operation("employees", write=True)
def request_department_transfer(employee_id: str, target_department: str) -> dict:
    """Request a transfer to an existing department ID or exact department name, pending HR review."""
    p = self_access(employee_id)
    require(p["status"] == "active", "Only active employees may request transfers.")
    dept = one(
        "SELECT * FROM departments WHERE id=? OR lower(name)=lower(?)",
        (target_department, target_department),
    )
    require(dept is not None, "Target department not found.", "not_found")
    require(
        p["department_id"] != dept["id"], "Employee already belongs to that department."
    )
    existing = one(
        "SELECT id FROM requests WHERE kind='department_transfer' AND owner_id=? AND status='pending'",
        (employee_id,),
    )
    require(not existing, "A transfer is already pending.", "conflict")
    return pending(
        "department_transfer",
        employee_id,
        {"current_department": p["department_id"], "target_department": dept["id"]},
    )


@operation("employees")
def get_employee_manager(employee_id: str) -> dict:
    """Get own assigned manager's directory information."""
    p = self_access(employee_id, "hr")
    if not p["manager_id"]:
        return {"manager": None, "message": "No manager assigned."}
    return {
        "manager": one(
            "SELECT id employee_id,name,role FROM employees WHERE id=?",
            (p["manager_id"],),
        )
    }


@operation("employees")
def get_department_employees(department_id: str) -> dict:
    """List directory-only fields for a department ID or exact department name."""
    role("employee", "hr", "manager", "finance", "payroll")
    from services.common import department_id as resolve_department

    department_id = resolve_department(department_id)
    return {
        "employees": rows(
            "SELECT id employee_id,name,role FROM employees WHERE department_id=? ORDER BY name",
            (department_id,),
        )
    }


def checklist(kind, employee_id, payload):
    existing = one(
        "SELECT id,payload,status FROM requests WHERE kind=? AND owner_id=? AND status IN ('pending','approved')",
        (kind, employee_id),
    )
    if existing:
        return {
            "request_id": existing["id"],
            "status": existing["status"],
            "existing": True,
            **json.loads(existing["payload"]),
        }
    return {**pending(kind, employee_id, payload), **payload}


@operation("employees", write=True)
def create_onboarding(employee_id: str) -> dict:
    """Authorized HR creates or retrieves the standard employee onboarding checklist."""
    role("hr")
    p = employee(employee_id)
    require(p["status"] == "active", "Employee must be active.")
    return checklist(
        "onboarding",
        employee_id,
        {
            "tasks": [
                {"title": title, "status": "pending"}
                for title in policy("onboarding_tasks")
            ]
        },
    )


@operation("employees", write=True)
def start_offboarding(employee_id: str) -> dict:
    """HR-only pending offboarding checklist. Does not disable accounts or terminate employment."""
    role("hr")
    p = employee(employee_id)
    require(p["status"] == "active", "Employee must be active.")
    return checklist(
        "offboarding",
        employee_id,
        {
            "departure_date": None,
            "tasks": [
                {"title": title, "status": "pending"}
                for title in policy("offboarding_tasks")
            ],
            "account_disable": False,
            "approval": "Authorized HR human review required",
        },
    )


@operation("employees")
def get_probation_status(employee_id: str) -> dict:
    """HR or self calculates probation end date from hire date and configured duration."""
    p = self_access(employee_id, "hr")
    end = day(p["hire_date"]) + timedelta(days=policy("probation_days"))
    return {
        "employee_id": employee_id,
        "hire_date": p["hire_date"],
        "probation_end": str(end),
        "status": "completed" if today() >= end else "in_probation",
    }


@operation("employees", write=True)
def request_employment_document(employee_id: str, document_type: str) -> dict:
    """Request own employment_verification or salary_certificate document for human preparation."""
    self_access(employee_id)
    require(document_type in policy("document_types"), "Unsupported document type.")
    return pending("employment_document", employee_id, {"document_type": document_type})


@operation("employees")
def check_training_eligibility(employee_id: str, course_id: str) -> dict:
    """Check own course prerequisites, capacity, existing enrollment and active status."""
    p = self_access(employee_id, "hr")
    course = one("SELECT * FROM courses WHERE id=?", (course_id,))
    require(course is not None, "Course not found.", "not_found")
    missing = sorted(
        set(json.loads(course["prerequisites"])) - set(json.loads(p["skills"]))
    )
    enrolled = (
        one(
            "SELECT 1 FROM enrollments WHERE employee_id=? AND course_id=?",
            (employee_id, course_id),
        )
        is not None
    )
    available = (
        course["capacity"]
        - one("SELECT count(*) n FROM enrollments WHERE course_id=?", (course_id,))["n"]
    )
    reasons = []
    if p["status"] != "active":
        reasons.append("Employee is not active.")
    if missing:
        reasons.append("Missing prerequisites: " + ", ".join(missing))
    if enrolled:
        reasons.append("Already enrolled.")
    if available <= 0:
        reasons.append("Course is full.")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "available_places": max(0, available),
        "missing_prerequisites": missing,
    }
