"""Single source for operation input contracts and discoverable authorization notes.

Service signatures own names/types/defaults. Shared field definitions enrich them
without copying 60 signatures. Calendar strings stay ISO strings for API/service
compatibility; Pydantic validates their actual calendar values before dispatch.
"""

import inspect
import re
from datetime import date, time
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    model_validator,
)


def iso_date(value):
    parsed = date.fromisoformat(value)
    if not 1900 <= parsed.year <= 2200:
        raise ValueError("Date year must be between 1900 and 2200.")
    return value


def iso_month(value):
    iso_date(value + "-01")
    return value


def clock_time(value):
    time.fromisoformat(value)
    return value


def date_period(value):
    start, end = value.split("/")
    iso_date(start)
    iso_date(end)
    if start > end:
        raise ValueError("End date must be on or after start date.")
    if (date.fromisoformat(end) - date.fromisoformat(start)).days > 366:
        raise ValueError("Date range must be no longer than 367 days.")
    return value


def money_precision(value):
    cents = Decimal(str(value)) * 100
    if cents != cents.to_integral_value():
        raise ValueError("Amount must have at most two decimal places.")
    return value


ISODate = Annotated[
    str,
    Field(pattern=r"^\d{4}-\d{2}-\d{2}$", json_schema_extra={"format": "date"}),
    AfterValidator(iso_date),
]
Month = Annotated[str, Field(pattern=r"^\d{4}-\d{2}$"), AfterValidator(iso_month)]
Clock = Annotated[str, Field(pattern=r"^\d{2}:\d{2}$"), AfterValidator(clock_time)]
Period = Annotated[
    str,
    Field(pattern=r"^\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}$"),
    AfterValidator(date_period),
]
Identifier = Annotated[
    str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
]
Nonblank = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]
Amount = Annotated[
    float,
    Field(gt=0, le=100_000_000, allow_inf_nan=False),
    AfterValidator(money_precision),
]

# Descriptions include provenance: knowing an employee ID never grants access.
FIELDS = {
    "employee_id": (
        Identifier,
        "Target stable employee ID, e.g. E001. For self-service use the trusted application employee_id; for another employee resolve their exact name with get_employee. Never invent an ID; authorization is checked independently.",
    ),
    "employee_ids": (
        Annotated[list[Identifier], Field(min_length=1, max_length=100)],
        "Distinct stable employee IDs for the proposed simultaneous leave. Resolve named colleagues; HR/assigned-manager authorization is required.",
    ),
    "target_employee_id": (
        Identifier,
        "Stable ID of the explicitly named colleague receiving the shift swap; resolve with get_employee, never guess.",
    ),
    "assignee_id": (
        Identifier,
        "Stable ID of the explicitly named task assignee; resolve with get_employee. Do not substitute the current employee unless requested.",
    ),
    "start_date": (
        ISODate,
        "First inclusive date, YYYY-MM-DD with an explicit year. Ask if the date or year is missing/ambiguous.",
    ),
    "end_date": (
        ISODate,
        "Last inclusive date, YYYY-MM-DD with an explicit year, on/after start_date. Do not infer an end date from vague duration.",
    ),
    "new_start_date": (
        ISODate,
        "Replacement first inclusive leave date, YYYY-MM-DD with explicit year.",
    ),
    "new_end_date": (
        ISODate,
        "Replacement last inclusive leave date, YYYY-MM-DD with explicit year, on/after new_start_date.",
    ),
    "date": (
        ISODate,
        "Specific attendance/remote-work calendar date, YYYY-MM-DD with explicit year. A precise relative date may be resolved from the trusted company-local date.",
    ),
    "shift_date": (
        ISODate,
        "Exact assigned shift date, YYYY-MM-DD with explicit year; ask if ambiguous.",
    ),
    "due_date": (
        ISODate,
        "Task deadline, YYYY-MM-DD with explicit year; required even when project/title/assignee are known.",
    ),
    "month": (
        Month,
        "Calendar month YYYY-MM, including year. Ask for an omitted year; do not assume the current year.",
    ),
    "date_range": (
        Period,
        "Inclusive date range formatted YYYY-MM-DD/YYYY-MM-DD; both endpoints and years are required.",
    ),
    "period": (
        Period,
        "Inclusive timesheet period formatted YYYY-MM-DD/YYYY-MM-DD; both endpoints and years are required.",
    ),
    "corrected_time": (
        Clock,
        "Requested replacement check-in time in company-local HH:MM, 24-hour format. Does not directly overwrite attendance.",
    ),
    "year": (
        Annotated[int, Field(ge=1900, le=2200)],
        "Explicit calendar year, e.g. 2026. Ask unless the request explicitly refers to this/current year.",
    ),
    "request_id": (
        Annotated[int, Field(gt=0)],
        "Positive existing leave request ID. Require the user to identify the request; never choose an arbitrary request from history.",
    ),
    "ticket_id": (
        Annotated[int, Field(gt=0)],
        "Positive existing ticket reference supplied by the user or unambiguously returned by an authorized lookup. Never invent it.",
    ),
    "task_id": (
        Annotated[int, Field(gt=0)],
        "Positive existing task ID. If a title matches multiple tasks, ask which ID; do not update an arbitrary task.",
    ),
    "quantity": (
        Annotated[int, Field(gt=0)],
        "Explicit positive integer quantity. Words such as some or a few do not specify a quantity; ask the user.",
    ),
    "amount": (
        Amount,
        "Explicit positive EGP amount with at most two decimal places. Do not infer an amount, currency conversion or budget approval.",
    ),
    "hours": (
        Annotated[float, Field(gt=0, le=24, allow_inf_nan=False)],
        "Explicit positive overtime hours for the given date. Recorded-hours and policy limits are checked by the service.",
    ),
    "decision": (
        Literal["approve", "reject"],
        "Explicit manager decision: approve or reject. Assigned-manager permission and separate human confirmation are required.",
    ),
    "status": (
        Literal["pending", "in_progress", "completed"],
        "Requested exact task status. Allowed transitions and assignee/manager permission are enforced by the service.",
    ),
    "field": (
        Literal["phone", "preferred_name"],
        "Approved own-profile field only: phone or preferred_name. Roles, salary and permissions cannot be changed.",
    ),
    "value": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Explicit replacement profile value supplied by the user; never fabricate contact information.",
    ),
    "name": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Explicit employee name, matched exactly ignoring surrounding whitespace and case. Partial/ambiguous names must be clarified; directory data only.",
    ),
    "department_id": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Known department ID or exact name, e.g. ENG or Engineering; the backend resolves the canonical ID.",
    ),
    "target_department": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Explicit requested destination department ID or exact name; never choose a destination for the employee.",
    ),
    "project_id": (
        Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")],
        "Known project ID or exact project name, e.g. ALPHA or Project Alpha. Ask which project if omitted.",
    ),
    "item_id": (
        Identifier,
        "Inventory item ID returned by check_inventory, e.g. LAPTOP. Resolve an item name through stock lookup rather than inventing an ID.",
    ),
    "item_name": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Exact inventory item name, e.g. laptops or mice. This is a stock lookup, not a device request.",
    ),
    "asset_id": (
        Identifier,
        "Known assigned device asset ID, e.g. ASSET-1. Ask for the asset reference if missing; ownership is enforced.",
    ),
    "course_id": (
        Identifier,
        "Exact training course ID supplied by the user; unknown IDs are rejected by the service.",
    ),
    "order_id": (
        Identifier,
        "Exact customer order reference, e.g. ORD-1. Ask for the order ID; never select an arbitrary order.",
    ),
    "invoice_id": (
        Identifier,
        "Exact invoice reference, e.g. INV-100; finance authorization is required.",
    ),
    "vendor_id": (
        Identifier,
        "Known vendor reference for duplicate-invoice detection; do not invent a vendor.",
    ),
    "invoice_number": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Vendor invoice number exactly as supplied; distinct from the internal invoice ID.",
    ),
    "policy_type": (
        Literal["annual", "carryover"],
        "Exact leave policy type: annual or carryover. Use search_hr_policy for other company policies.",
    ),
    "document_type": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Explicit document type, e.g. employment_verification or salary_certificate; supported types are checked against current policy.",
    ),
    "category": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "User-provided case/expense category. Reimbursement categories are checked against current configured policy.",
    ),
    "receipt_reference": (
        Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")],
        "Actual demo receipt reference supplied by the user; required for reimbursement. Never invent a receipt.",
    ),
    "issue_description": (
        Nonblank,
        "User-provided description of the IT/payroll problem, 1–2000 characters; do not invent symptoms or financial facts.",
    ),
    "description": (
        Nonblank,
        "User-provided HR case or purchase description, 1–2000 characters. Ask when the purpose/content is missing.",
    ),
    "reason": (
        Nonblank,
        "User-provided reason for customer complaint escalation, 1–2000 characters.",
    ),
    "new_address": (
        Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")],
        "Complete new fictional shipping address supplied by the customer; never invent an address.",
    ),
    "software_name": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Explicit software product name, e.g. Microsoft Office; availability and existing assignments are checked by the service.",
    ),
    "device_type": (
        Annotated[str, Field(min_length=1, max_length=100, pattern=r"\S")],
        "Requested device type: laptop/laptops or mouse/mice. Use request_inventory_item when an explicit bulk quantity is requested.",
    ),
    "title": (
        Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")],
        "Explicit task title supplied by the user. Naming the assignee alone is insufficient.",
    ),
    "query": (
        Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")],
        "Specific HR policy topic to search, such as remote work. This does not search private records.",
    ),
}

# Human-readable contracts mirror existing enforcement; services remain authoritative.
AUTHORIZATION = {}


def _authorize(rule, names):
    for name in names.split():
        AUTHORIZATION[name] = rule


_authorize(
    "Self employee only; identity is supplied by the local application, never proven by the argument.",
    """request_leave cancel_leave modify_leave report_missing_checkout request_overtime request_shift_swap request_remote_work request_attendance_correction update_employee_profile request_department_transfer request_employment_document create_payroll_ticket submit_expense_request create_hr_case create_it_ticket request_software_license request_company_device request_inventory_item request_expense_approval""",
)
_authorize(
    "Self employee or authorized HR role.",
    """get_leave_balance check_leave_overlap calculate_leave_days get_leave_history calculate_leave_carryover check_leave_eligibility get_attendance check_late_arrivals validate_timesheet get_employee_manager get_probation_status check_training_eligibility""",
)
_authorize(
    "Internal employee directory/policy access only; no customer access or private payroll fields.",
    """get_leave_policy get_employee get_department_employees search_hr_policy check_inventory get_low_stock_items check_inventory_request get_restock_status""",
)
_authorize(
    "Authorized HR role only; creates a pending human-reviewed workflow.",
    "create_onboarding start_offboarding",
)
_authorize(
    "Assigned manager only; cannot review own leave; rechecked at confirmation.",
    "review_leave_request",
)
_authorize(
    "HR role or assigned manager of every requested employee.",
    "check_team_leave_conflict",
)
_authorize(
    "Self employee or authorized payroll role; fictional payslip only.", "get_payslip"
)
_authorize(
    "Owner of the IT ticket only; payroll/HR/customer tickets excluded.",
    "get_it_ticket_status",
)
_authorize("Assigned owner of the device only.", "check_device_warranty")
_authorize(
    "Selected customer must own the order.",
    "get_order_status request_product_return check_return_eligibility update_shipping_address",
)
_authorize(
    "Selected customer must own the open customer complaint ticket.",
    "escalate_customer_ticket",
)
_authorize(
    "Authorized finance role only.",
    "get_invoice_status check_duplicate_invoice get_overdue_invoices",
)
_authorize(
    "Finance role or manager of the requested department.", "check_department_budget"
)
_authorize(
    "Project membership required; assignee must be an active project member.",
    "create_project_task",
)
_authorize("Project membership required.", "get_overdue_tasks get_project_progress")
_authorize(
    "Self or assigned manager; results restricted to projects the caller belongs to.",
    "check_task_deadline_conflicts",
)
_authorize(
    "Task assignee or their assigned manager, plus project membership.",
    "update_task_status",
)


class OperationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def validate_relationships(self):
        for start, end in [
            ("start_date", "end_date"),
            ("new_start_date", "new_end_date"),
        ]:
            if hasattr(self, start) and hasattr(self, end):
                a, b = getattr(self, start), getattr(self, end)
                if a > b:
                    raise ValueError(f"{end} must be on or after {start}.")
                if (date.fromisoformat(b) - date.fromisoformat(a)).days > 366:
                    raise ValueError("Date range must be no longer than 367 days.")
        ids = getattr(self, "employee_ids", None)
        if ids is not None and len(ids) != len(set(ids)):
            raise ValueError("employee_ids must contain distinct IDs.")
        if getattr(self, "field", None) == "phone" and not re.fullmatch(
            r"\+?[0-9 ()-]{7,25}", self.value.strip()
        ):
            raise ValueError("Invalid phone format.")
        return self


def build_schema(fn):
    fields = {}
    for name, param in inspect.signature(fn).parameters.items():
        if name not in FIELDS:
            raise ValueError(f"Missing input contract for {fn.__name__}.{name}")
        annotation, description = FIELDS[name]
        if fn.__name__ == "get_leave_balance" and name == "year":
            description = "Optional calendar year (1900–2200). Omitted/null uses current year. Explicit years must come from the user or unambiguous active Studio conversation context."
        default = ... if param.default is inspect.Parameter.empty else param.default
        # Required has no default; optional follows the actual service signature.
        if default is None:
            annotation = annotation | None
        fields[name] = (annotation, Field(default=default, description=description))
    return create_model(fn.__name__ + "_input", __base__=OperationInput, **fields)


def validation_failure(exc, operation=None):
    """Safe structured errors, excluding input values, traces and library URLs."""
    errors = [
        {
            "field": ".".join(map(str, e["loc"])) or "__root__",
            "type": e["type"],
            "message": e["msg"],
        }
        for e in exc.errors(
            include_url=False, include_context=False, include_input=False
        )
    ]
    missing = [e["field"] for e in errors if e["type"] == "missing"]
    return {
        "ok": False,
        "code": "validation_error",
        "operation": operation,
        "error": (
            "Missing required information."
            if missing
            else "Invalid operation arguments."
        ),
        "missing_fields": missing,
        "errors": errors,
        "clarification_required": bool(missing),
        "next_step": (
            "Ask for the missing fields; use trusted identity for self-service IDs. Do not invent values."
            if missing
            else "Explain the field errors and ask for corrected information. Do not retry with guessed values."
        ),
    }
