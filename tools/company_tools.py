"""Eleven stable tools with registry-derived catalogs and typed envelopes."""

import json
from typing import Any, Literal
from langchain.tools import tool
from pydantic import BaseModel, ConfigDict, Field, create_model
from services import (
    hr,
    attendance,
    employees,
    support,
    inventory,
    customers,
    finance,
    projects,
)
from services.common import SCHEMAS, METADATA, execute, operation_details, ACTOR
from database import connect
from operation_schemas import validation_failure
from pydantic import ValidationError
from tools.input_context import calendar_guard

MODULE_GUIDANCE = {
    "hr": "Use for annual leave balances, date calculations, eligibility, history, requests and assigned-manager review. For general company policies use payroll_operations/search_hr_policy. Missing leave dates/year or request_id require clarification.",
    "attendance": "Use for recorded attendance, lateness, timesheets, overtime, correction, remote-work and shift-swap requests. Do not use it to request vacation or change approved records directly. Ask for missing dates, hours, correction time or target colleague.",
    "employees": "Use for directory teams/managers, permitted own-profile edits, transfer/document requests, onboarding/offboarding, probation and training eligibility. Use get_employee to resolve a named person; do not use directory lookup for private payroll data.",
    "payroll": "Use for own/authorized fictional payslips, payroll support, expense reimbursements with receipt/category, restricted HR cases and HR policy search. Use finance_operations for purchase approval/budgets/invoices. Missing reimbursement amount or receipt requires clarification.",
    "it": "Use for IT tickets/status, one-device requests, licenses and own-device warranty. Use inventory_operations/request_inventory_item for explicit bulk quantities; never silently convert a vague bulk request into one device.",
    "inventory": "Use for stock, low-stock, restock, request-limit checks and quantity-based inventory requests. A quantity question is a read-only check, not a request. Ask how many if quantity is missing; use it_operations for individual assigned-device support.",
    "customers": "Use for the selected customer’s order status, return eligibility/request, pre-shipment address update and complaint escalation. Ask for missing order/ticket reference or new address; internal employees are not customer identities.",
    "finance": "Use for authorized invoice status/duplicates, department budget checks, purchase approval requests and overdue invoices. get_invoice_status requires ONLY invoice_id; do not ask for vendor_id or amount (those are for check_duplicate_invoice). Use payroll_operations for a personal receipt reimbursement. Do not invent invoice/vendor numbers or amounts.",
    "projects": "Use for member-scoped task creation, status updates, overdue work, deadline conflicts and project progress. Creation requires project, assignee, title and due date. A vague task title/reference must be clarified before updating a task.",
}


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DescribeInput(ToolInput):
    operation: str = Field(
        min_length=1,
        max_length=100,
        description="Exact operation name from a module catalog. Unknown names return the available catalog; no business operation executes.",
    )


def trusted_context():
    if ACTOR.get() is None:
        return {}
    connection = connect()
    try:
        row = connection.execute(
            "SELECT employee_id,customer_id FROM users WHERE id=?", (ACTOR.get(),)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        connection.close()


def dispatch(module, operation, arguments):
    if operation not in METADATA or METADATA[operation]["module"] != module:
        return {
            "ok": False,
            "error": "Operation does not belong to this module.",
            "code": "invalid_request",
            "available_operations": [
                n for n, m in METADATA.items() if m["module"] == module
            ],
        }
    try:
        validated = SCHEMAS[operation].model_validate(arguments).model_dump()
    except ValidationError as exc:
        failure = validation_failure(exc, operation)
        context = trusted_context()
        if "employee_id" in failure["missing_fields"] and context.get("employee_id"):
            failure["trusted_context"] = context
            failure["clarification_required"] = any(
                field != "employee_id" for field in failure["missing_fields"]
            )
            failure["next_step"] = (
                "For a self-service request employee_id is already available in trusted_context: use that exact ID, do not ask the user for it. For a named colleague use get_employee. Ask only for other missing required fields; never guess them."
            )
        return failure
    blocked = calendar_guard(validated)
    if blocked:
        return {**blocked, "operation": operation}
    return execute(operation, validated)


@tool(args_schema=DescribeInput)
def describe_operation(operation: str) -> dict:
    """Inspect exact required/optional arguments, types, constraints, authorization and confirmation for one operation before dispatch. Read-only metadata, no business changes. Use names in module catalogs; unknown names return the catalog. This does not retrieve employee facts or execute an operation."""
    if operation not in SCHEMAS:
        return {
            "ok": False,
            "error": "Unknown operation.",
            "code": "not_found",
            "available": [
                {
                    "operation": n,
                    "tool": (
                        "get_employee"
                        if n == "get_employee"
                        else m["module"] + "_operations"
                    ),
                    "description": m["description"],
                }
                for n, m in METADATA.items()
            ],
        }
    return {**operation_details(operation), "trusted_context": trusted_context()}


@tool(args_schema=SCHEMAS["get_employee"])
def get_employee(name: str) -> dict:
    """Look up public employee directory fields and a stable employee_id using an explicit exact name, ignoring case and surrounding whitespace. Read-only; use to resolve named colleagues, not private salary or leave records. If name is absent/partial/ambiguous, ask which employee; never guess a match. Private records require the appropriate module and independent authorization."""
    result = execute("get_employee", {"name": name})
    return (
        result["data"]
        if result["ok"]
        else {"error": result["error"], "code": result.get("code")}
    )


def module_tool(module):
    names = [
        n for n, m in METADATA.items() if m["module"] == module and n != "get_employee"
    ]
    # The LLM sees an enum rather than arbitrary operation strings. Canonical
    # per-operation schemas remain in SCHEMAS, shared by discovery/API/services.
    envelope = create_model(
        module + "_tool_input",
        __base__=ToolInput,
        operation=(
            Literal[tuple(names)],
            Field(
                description="Choose the exact action from this module catalog. Inspect its schema with describe_operation before dispatch."
            ),
        ),
        arguments=(
            dict[str, Any],
            Field(
                description="Exact operation arguments from describe_operation; include every required field and no extras. Use {} for no-argument operations. Ask for missing values instead of inventing them. For self-service use the application-selected employee_id."
            ),
        ),
    )
    catalog = []
    for name in names:
        contract = operation_details(name)
        signature = ", ".join(
            key if field.is_required() else key + "?"
            for key, field in SCHEMAS[name].model_fields.items()
        )
        mode = (
            "WRITE PROPOSAL, human confirmation" if contract["write"] else "READ ONLY"
        )
        catalog.append(f"{name}({signature}) [{mode}]: {contract['description']}")
    description = (
        MODULE_GUIDANCE[module]
        + "\nOperations (all listed arguments required unless marked ?):\n"
        + "\n".join(catalog)
        + "\nFirst inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action."
    )

    @tool(module + "_operations", description=description, args_schema=envelope)
    def run(operation: str, arguments: dict) -> dict:
        return dispatch(module, operation, arguments)

    return run


COMPANY_TOOLS = [get_employee, describe_operation] + [
    module_tool(module) for module in MODULE_GUIDANCE
]
for exposed_tool in COMPANY_TOOLS:
    # Structural envelope errors must be returned to the model, not abort the
    # graph or expose raw input values and Pydantic implementation details.
    exposed_tool.handle_validation_error = lambda error: json.dumps(
        validation_failure(error)
    )
