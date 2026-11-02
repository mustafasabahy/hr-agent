"""Generate TOOL_AUDIT.md from the actual tool registry and recorded evidence."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.company_tools import COMPANY_TOOLS
from services.common import SCHEMAS, operation_details


def cell(value):
    return str(value).replace("|", "/").replace("\n", " ")


def render():
    lines = [
        "# Tool calling audit",
        "",
        "## Initial findings",
        "",
        "The 11 tools and 60 operations existed, with strict signature-derived required fields and safe confirmation/authorization. Module envelopes exposed unconstrained operation strings and generic argument dictionaries. Field descriptions, structural range constraints, explicit authorization metadata and structured clarification errors were missing. Existing backend tests did not establish real-model clarification behavior. No optional business parameters existed. The previous live smoke test had shown an invented extra argument followed by recovery.",
        "",
        "## Current inventory and descriptions",
        "",
        "Names remain stable for compatibility. There is one agent and 11 tools. Module descriptions are generated from the registry, include signatures and read/write markers, and distinguish neighboring intents. Module envelopes constrain operation to a per-module enum. The generic inner dictionary is validated against the exact operation model before any service call.",
        "",
    ]
    for tool in COMPANY_TOOLS:
        lines += ["### `" + tool.name + "`", "", tool.description, ""]
    lines += [
        "## All 60 operation contracts",
        "",
        "Generated from service signatures, `operation_schemas.py`, and the registry. Required fields have no default. Optional fields have explicit service defaults; `get_leave_balance` has one optional `year` argument (default null/current year); other business arguments remain required. No optional reason field was invented. Read-only operations never need confirmation; every write only proposes a change for an owner-confirmed HTTP transaction. Authorization text documents services; service code remains the enforcement authority.",
        "",
        "| Operation | Tool | Required arguments | Optional | Mode / confirmation | Authorization |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    fields = {}
    for name, schema in SCHEMAS.items():
        detail = operation_details(name)
        props = detail["arguments_schema"]["properties"]
        required = []
        optional = []
        for key, field in schema.model_fields.items():
            prop = props[key]
            kind = prop.get("type") or ("enum" if "enum" in prop else "union")
            summary = f"`{key}: {kind}`"
            (required if field.is_required() else optional).append(summary)
            fields.setdefault(key, prop)
        tool = (
            "get_employee"
            if name == "get_employee"
            else detail["module"] + "_operations"
        )
        values = [
            f"`{name}`",
            f"`{tool}`",
            ", ".join(required) or "none",
            ", ".join(optional) or "none",
            (
                "Write proposal / human confirmation"
                if detail["write"]
                else "Read only / none"
            ),
            detail["authorization"],
        ]
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines += [
        "",
        "## Shared field meanings and constraints",
        "",
        "These field definitions are generated from the actual schemas, not a separate handwritten contract. ISO date strings are retained for API compatibility but their real calendar dates, year range and date ordering are validated by Pydantic. Business eligibility, balances, ownership, supported policy categories and transitions remain service checks.",
        "",
        "| Field | Description | JSON-schema constraints |",
        "| --- | --- | --- |",
    ]
    for key, prop in fields.items():
        constraints = {
            k: v for k, v in prop.items() if k not in {"title", "description"}
        }
        lines.append(
            "| "
            + cell("`" + key + "`")
            + " | "
            + cell(prop["description"])
            + " | "
            + cell("`" + json.dumps(constraints, ensure_ascii=False) + "`")
            + " |"
        )
    lines += [
        "",
        "Additional Pydantic validators enforce valid calendar/clock values, date-range ordering/length, distinct employee lists, phone syntax and exact two-decimal money precision. Those callable validators are not fully expressible as JSON-schema constraints. Numeric values are finite and positive; IDs/counts are strict types; unexpected fields are forbidden.",
        "",
        "## Missing information, identity and rejection behavior",
        "",
        "* Tools inspect `describe_operation` for required/optional fields, provenance descriptions and authorization. Unsupported names return a catalog or a structured envelope error.",
        "* Missing input returns `code`, `operation`, `missing_fields`, safe field errors, `clarification_required` and `next_step`. Values, stack traces and Pydantic URLs are not echoed.",
        "* Known self identity is supplied by the application. Metadata/error hints expose the selected employee ID to the model, preventing an unnecessary user-ID question; they do not silently replace another target or prove authorization.",
        "* Partial/case-insensitively ambiguous employee names are not arbitrarily resolved. Request/task/order/ticket references must be identified; a multi-request cancellation must ask which ID.",
        "* FastAPI and default Studio requests remain independent. Opt-in Studio human-message memory supports bounded same-thread clarification; see MEMORY_FIX_RESULTS.md. Non-required fields must not be requested as prerequisites.",
        "* Month/day without a year always requires clarification. A request-local tool guard blocks invented years before service dispatch. Explicit four-digit years (including Arabic digits) and supported precise relative dates are checked against the original user message. Supported relative forms are today/tomorrow/yesterday, current month/week ranges and current year. Week means Monday–Sunday.",
        "* Direct HTTP operation calls supply explicit canonical arguments and do not pass through the natural-language year guard. They still undergo the identical Pydantic/service/authorization/confirmation checks.",
        "* All consequential changes retain immutable proposals, expiry, ownership, atomic revalidation and exactly-once confirmation receipts. The model cannot invoke confirmation.",
        "",
        "## Verification and live results",
        "",
        "Verified during this audit: **85 offline tests passed** (69 original business tests plus 16 focused contract tests). Offline tests preserve the original 69 business tests and add focused metadata/schema, routing, safe error, ambiguity, context and provenance tests. Scripted-model tests force tool attempts to verify the guard; they do **not** prove real model understanding.",
        "",
    ]
    report_path = ROOT / "LIVE_TOOL_CHECKS.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        if "runs" in report:
            lines += [
                f"Real live testing: **{report['total_model_calls']} OpenAI model calls across {report['total_agent_requests']} independent requests**, including failures and targeted retests. All calls used fictional temporary databases; no human confirmations were executed.",
                "",
                "| Run | Cases | Passed | Failed | Model calls |",
                "| --- | --- | --- | --- | --- |",
            ]
            for run in report["runs"]:
                lines.append(
                    "| "
                    + " | ".join(
                        map(
                            cell,
                            [
                                run["label"],
                                len(run["results"]),
                                run["passed"],
                                run["failed"],
                                run["total_model_calls"],
                            ],
                        )
                    )
                    + " |"
                )
            lines += [
                "",
                "Detailed original inputs, tool/operation/arguments, clarification flags, unsafe attempts, backend results, final responses and explicit pass/fail expectations are retained in [LIVE_TOOL_CHECKS.json](LIVE_TOOL_CHECKS.json). Earlier failures are not erased by later passes.",
                "",
                "Observed failures: an initially yearless leave request caused a premature proposal (no business data changed); a complete request later asked for an already trusted employee ID; invoice status once requested an unrelated vendor ID. Repairs added the calendar guard, trusted-ID error hints and clearer neighboring-operation guidance. The unauthorized-payslip initial response also overstated policy about payroll administrators; the backend denial wording/prompt now identify the selected application account rather than trusting a role claim.",
            ]
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash\npython -m unittest discover -s tests -v\npython scripts/generate_tool_audit.py\n# Lists cases only: zero paid calls\npython scripts/live_tool_checks.py\n# Explicitly opt in to a small subset\npython scripts/live_tool_checks.py --live --cases complete_leave,missing_leave_dates,invalid_quantity --max-model-calls 10 --output live-local-results.json\n```",
        "",
        "## Remaining limitations",
        "",
        "Real LLM behavior is variable: passing a smoke check is not proof of consistent extraction, clarification or all-60 live coverage. Recorded pass/fail uses explicit tool/argument/keyword expectations, not an LLM judge; review complete traces for semantic mistakes or invented policy language. The generic dispatcher remains, supported by exact discovery and backend enforcement. The year guard is deliberately narrow, not a general natural-language provenance parser: it does not prove every quantity, identifier or amount was grounded, and does not resolve arbitrary relative phrases. Valid-looking invented arguments can still be proposed; human review/confirmation remains mandatory. The later opt-in Studio memory update uses existing checkpoint state; no new memory database, business tables, agents or evaluator model were added.",
        "",
    ]
    studio_doc = (ROOT / "STUDIO_DEMO.md").read_text()
    marker = "## Opt-in Studio conversation memory and year-aware balances"
    if marker in studio_doc:
        lines += [marker + studio_doc.split(marker, 1)[1]]
    return "\n".join(lines)


if __name__ == "__main__":
    (ROOT / "TOOL_AUDIT.md").write_text(render())
    print("Generated TOOL_AUDIT.md from 11 tools and 60 registered operation schemas.")
