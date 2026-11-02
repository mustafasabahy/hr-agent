"""Real leave lifecycle demo; no application/business-rule modifications.

Default is preview only. --live uses one persistent Agent Server thread and stops
at proposals. Explicit console authorization is required for each HTTP commit.
The supplied DB must match both demo servers; the main company.db is prohibited.
"""

import argparse
import asyncio
import ipaddress
import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import httpx
from dotenv import load_dotenv
from langgraph_sdk import get_client


class DemoError(Exception):
    pass


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data/leave-workflow-demo.db"
DEFAULT_REPORT = ROOT / "LEAVE_WORKFLOW_RESULTS.json"
PLANNED_START = "2027-01-11"
PLANNED_END = "2027-01-15"


def utc():
    return datetime.now(timezone.utc).isoformat()


def connect_readonly(path):
    path = path.resolve()
    if path == (ROOT / "data/company.db").resolve() or path.name == "company.db":
        raise DemoError("Use an isolated demo DB, never company.db.")
    return sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True)


def snapshot(path, year):
    c = connect_readonly(path)
    c.row_factory = sqlite3.Row
    try:

        def rows(sql, params=()):
            return [dict(r) for r in c.execute(sql, params)]

        person = rows(
            "SELECT id,name,department_id,manager_id,hire_date,status FROM employees WHERE id='E001'"
        )
        user = rows("SELECT id,employee_id,roles FROM users WHERE id='ahmed'")
        if (
            not person
            or person[0]["name"] != "Ahmed"
            or not user
            or user[0]["employee_id"] != "E001"
        ):
            raise DemoError("Fictional Ahmed/E001 mapping not verified.")
        requests = rows(
            "SELECT * FROM leave_requests WHERE employee_id='E001' ORDER BY id"
        )
        settings = {
            r["key"]: json.loads(r["value"])
            for r in rows(
                "SELECT * FROM settings WHERE key IN ('annual_allowance','weekends','eligibility_days')"
            )
        }
        company_today = datetime.now(
            ZoneInfo(os.getenv("COMPANY_TIMEZONE", "Europe/Berlin"))
        ).date()
        balances = {}
        for y in sorted({company_today.year, year}):
            allowance = rows(
                "SELECT annual_allowance FROM leave_balances WHERE employee_id='E001' AND year=?",
                (y,),
            )
            allowance = (
                allowance[0]["annual_allowance"]
                if allowance
                else settings["annual_allowance"]
            )
            used = sum(
                r["deducted_days"]
                for r in requests
                if r["status"] == "approved" and r["start_date"][:4] == str(y)
            )
            balances[str(y)] = {
                "year": y,
                "annual_allowance": allowance,
                "used_days": used,
                "remaining_days": allowance - used,
            }
        return {
            "recorded_at": utc(),
            "company_local_date": str(company_today),
            "employee": person[0],
            "identity": user[0],
            "manager": rows(
                "SELECT u.id demo_user,e.id employee_id,e.name,u.roles FROM employees e JOIN users u ON u.employee_id=e.id WHERE e.id=?",
                (person[0]["manager_id"],),
            ),
            "balances": balances,
            "requests": requests,
            "pending_requests": [r for r in requests if r["status"] == "pending"],
            "approved_requests": [r for r in requests if r["status"] == "approved"],
            "holidays": rows("SELECT * FROM holidays ORDER BY day"),
            "weekends": settings["weekends"],
            "eligibility_days": settings["eligibility_days"],
            "confirmations": rows(
                "SELECT id,actor_id,operation,arguments,status,expires_at,result FROM confirmations ORDER BY created_at"
            ),
        }
    finally:
        c.close()


def business_signature(state):
    return {"balances": state["balances"], "requests": state["requests"]}


def parse_run(values):
    messages = values.get("messages", [])
    calls = []
    outputs = []
    for m in messages:
        for call in m.get("tool_calls", []):
            arguments = call.get("args", {})
            tool = call["name"]
            calls.append(
                {
                    "id": call["id"],
                    "tool": tool,
                    "operation": (
                        tool if tool == "get_employee" else arguments.get("operation")
                    ),
                    "arguments": (
                        arguments
                        if tool == "get_employee"
                        else arguments.get("arguments", {})
                    ),
                }
            )
        if m.get("type", m.get("role")) == "tool":
            try:
                output = json.loads(m["content"])
            except (ValueError, TypeError):
                output = {"text": m.get("content")}
            outputs.append({"tool_call_id": m.get("tool_call_id"), "output": output})
    return {
        "messages": messages,
        "tool_calls": calls,
        "tool_results": outputs,
        "final_response": next(
            (
                m.get("content", "")
                for m in reversed(messages)
                if m.get("type", m.get("role")) in ["ai", "assistant"]
            ),
            "",
        ),
        "completed_model_calls": sum(
            m.get("type", m.get("role")) in ["ai", "assistant"] for m in messages
        ),
    }


def remote_trace(run_id, expected_models=None):
    # Authenticated reads only; do not print raw SDK/provider errors or keys.
    from langsmith import Client
    import warnings

    c = Client()
    for attempt in range(5):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                run = c.read_run(run_id, load_child_runs=True)
                project = c.read_project(project_name="company-agent-demo")
                url = c.get_run_url(run=run)
            children = []

            def walk(item):
                for child in item.child_runs or []:
                    children.append(child)
                    walk(child)

            walk(run)
            models = sum(r.run_type == "llm" for r in children)
            complete = bool(run.outputs) and (
                expected_models is None or models == expected_models
            )
            if not complete and attempt < 4:
                time.sleep(1)
                continue
            return {
                "status": (
                    "PASS"
                    if str(run.session_id) == str(project.id)
                    and complete
                    and not run.error
                    and not any(r.error for r in children)
                    else "FAIL"
                ),
                "run_id": str(run.id),
                "trace_id": str(run.trace_id),
                "url": url,
                "project": "company-agent-demo",
                "project_matches": str(run.session_id) == str(project.id),
                "model_runs": sum(r.run_type == "llm" for r in children),
                "tool_runs": [
                    {
                        "name": r.name,
                        "inputs": r.inputs,
                        "outputs": r.outputs,
                        "error": bool(r.error),
                    }
                    for r in children
                    if r.run_type == "tool"
                ],
                "has_errors": bool(run.error or any(r.error for r in children)),
                "final_output_available": bool(run.outputs),
            }
        except Exception as exc:
            if attempt == 4:
                return {"status": "NOT VERIFIED", "error_type": type(exc).__name__}
            time.sleep(1)


def save(report, path):
    report["updated_at"] = utc()
    report["total_completed_model_calls"] = sum(
        t.get("completed_model_calls", 0) for t in report.get("turns", [])
    )
    report["total_remote_model_runs"] = sum(
        t.get("langsmith", {}).get("model_runs", 0) for t in report.get("turns", [])
    )
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n"
    )
    render_document(report, path.with_name("LEAVE_WORKFLOW_DEMO.md"))


def render_document(r, path):
    start, end = r["requested_dates"]
    initial = r["initial_state"]
    final = r.get("latest_state", initial)
    lines = [
        "# Real leave workflow demonstration",
        "",
        f"Workflow `{r['workflow_id']}`; employee Ahmed/E001; one thread `{r.get('thread_id','not started')}`.",
        "",
        "## Scope and actual application limitations",
        "",
        "No application source/business rules were changed for this demonstration. The existing Studio before_agent hook discards older messages at each turn, so the same thread ID is persistent but relevant conversational memory is **not retained**. This acceptance criterion fails; successful fully restated turns do not prove memory. A separate fix proposal is provided for review only. get_leave_balance reports the current year; January 2027 usage must be checked against the actual 2027 ledger, not confused with 2026.",
        "",
        "## Initial state",
        "",
        f"Company-local date: {initial['company_local_date']}. Requested dates: {start} through {end}. Explicit January dates supersede the vague 'next month' in the first message; no dates were silently changed.",
        "",
        "```json",
        json.dumps(
            {
                "employee": initial["employee"],
                "manager": initial["manager"],
                "balances": initial["balances"],
                "pending_requests": initial["pending_requests"],
                "approved_requests": initial["approved_requests"],
                "weekends": initial["weekends"],
                "holidays": initial["holidays"],
            },
            indent=2,
        ),
        "```",
        "",
        "## Conversation and actual tool execution",
        "",
    ]
    for i, t in enumerate(r.get("turns", []), 1):
        lines += [
            f"### Turn {i}: {t['label']}",
            "",
            f"Input: {t['input']}",
            "",
            f"Actual response: {t.get('final_response','')}",
            "",
            "```json",
            json.dumps(
                {
                    "run_id": t["run_id"],
                    "tool_calls": t.get("tool_calls", []),
                    "tool_results": t.get("tool_results", []),
                },
                indent=2,
            ),
            "```",
            "",
            "LangSmith: "
            + (
                "[trace](" + t["langsmith"]["url"] + ")"
                if t.get("langsmith", {}).get("url")
                else t.get("langsmith", {}).get("status", "not checked")
            ),
            "",
        ]
    lines += [
        "## Backend validation versus separate tool calls",
        "",
        "`request_leave` internally invokes active-employment/tenure eligibility, actual working-day/holiday/weekend counting, same-year/future dates, pending/approved overlap and requested-year balance checks. Those internal functions are not separate agent tools. The write is executed for validation in a rolled-back savepoint before a proposal is stored. Coverage is reported; final manager approval rechecks staffing.",
        "",
        "Independent HTTP read checks below call the same existing services. They are explicitly **not agent tool calls**. Any separate validation operations actually selected by the model appear in the transcript above.",
        "",
        "```json",
        json.dumps(r.get("backend_read_checks", {}), indent=2),
        "```",
        "",
        "## Proposal, developer authorization and manager workflow",
        "",
        "```json",
        json.dumps(
            {
                "proposal": r.get("proposal"),
                "submission": {
                    key: value
                    for key, value in r.get(
                        "submission", {"status": "NOT AUTHORIZED / NOT EXECUTED"}
                    ).items()
                    if key not in ["before", "after"]
                },
                "manager_approval": {
                    key: value
                    for key, value in r.get(
                        "manager_approval", {"status": "NOT AUTHORIZED / NOT EXECUTED"}
                    ).items()
                    if key not in ["before", "after"]
                },
            },
            indent=2,
        ),
        "```",
        "",
        "Confirmation uses the existing FastAPI endpoint and matching demo-user header, never direct SQLite edits or a chat “yes”. Confirming submission only creates pending leave. Only a separately authorized assigned-manager review and confirmation deduct the requested-year balance. Completed confirmations return the same receipt on replay without another state change.",
        "",
        "## Latest database state and checks",
        "",
        "```json",
        json.dumps(
            {
                "balances": final["balances"],
                "requests": final["requests"],
                "checks": r.get("checks", {}),
                "phase": r["phase"],
            },
            indent=2,
        ),
        "```",
        "",
        "## Negative scenario",
        "",
        "```json",
        json.dumps(r.get("negative", {}), indent=2),
        "```",
        "",
        f"Completed OpenAI model calls observed in local messages: **{r.get('total_completed_model_calls',0)}**; remotely recorded model runs: **{r.get('total_remote_model_runs',0)}**. No evaluator model is used. Native responses/keyword checks are not a claim of universal LLM reliability.",
        "",
        "## Reproduce",
        "",
        "Use a dedicated database and the existing graph/app. Do not reset company.db. Configure .env locally; never paste secrets in chat or Studio.",
        "",
        '```bash\nsource .venv/bin/activate\nexport COMPANY_DB_PATH="$PWD/data/leave-workflow-demo.db"\nSTUDIO_DEMO_ENABLED=1 STUDIO_DEMO_USER=ahmed LANGSMITH_TRACING=true LANGCHAIN_TRACING_V2=true LANGSMITH_PROJECT=company-agent-demo langgraph dev --host 127.0.0.1 --port 2024\n# Another terminal with exactly the same COMPANY_DB_PATH (original 8000 remains untouched):\nCOMPANY_DB_PATH="$PWD/data/leave-workflow-demo.db" uvicorn main:app --host 127.0.0.1 --port 8001\npython demo_leave_workflow.py             # preview: no paid calls, no data changes\npython demo_leave_workflow.py --live      # one persistent thread, proposals only\npython demo_leave_workflow.py --live --resume --interactive\n```',
        "",
        "This recorded database already contains approved January leave. To repeat the full scenario, start both demo servers against a new isolated database filename and use a separate --report path; do not delete or reset the recorded database. Use --resume to inspect or continue this recorded run. Do not rerun --live over an existing result file without --resume or a separate --report path. Interactive turns use the same saved thread and fixed server identity. User confirmation/manager approval each require their own explicit console authorization:",
        "",
        "```bash\npython demo_leave_workflow.py --live --resume --confirm-submission\npython demo_leave_workflow.py --live --resume --prepare-manager-approval\npython demo_leave_workflow.py --live --resume --confirm-manager-approval\npython demo_leave_workflow.py --live --resume --post-check\n```",
        "",
        "The script prompts for an exact proposal-specific confirmation phrase before either commit. Never treat a model response as developer authorization. All commits use FastAPI; --prepare-manager-approval only prepares another proposal.",
        "",
        "## Studio presentation",
        "",
        "[Open the same Studio thread](https://smith.langchain.com/studio/thread?baseUrl=http://127.0.0.1:2024&threadId="
        + r.get("thread_id", "")
        + "). Select company_agent; expand each model/tools event, operation, arguments and output. Server checkpoints retain turn/run history for inspection even though the current model prompt drops prior turns. Different checkpoint-history views are not evidence of conversational memory.",
        "",
        "## Historical memory limitation and subsequent fix",
        "",
        "This original workflow evidence predates the approved memory/year implementation. Its recorded failures remain historical evidence and are not rewritten as passes. See MEMORY_FIX_RESULTS.md for the subsequent implementation, live retest and reproduction commands. Both original lifecycle approvals were received and executed in this recorded run; the memory retest performs no confirmations or approvals.",
        "",
    ]
    path.write_text("\n".join(lines))


async def turn(client, report, options, label, message):
    before = snapshot(options.database, report["request_year"])
    run = await client.runs.create(
        report["thread_id"],
        "company_agent",
        input={"messages": [{"role": "user", "content": message}]},
        metadata={
            "leave_workflow_id": report["workflow_id"],
            "leave_workflow_step": label,
        },
        config={"recursion_limit": 20},
    )
    await client.runs.join(report["thread_id"], run["run_id"])
    completed = await client.runs.get(report["thread_id"], run["run_id"])
    state = await client.threads.get_state(report["thread_id"])
    parsed = parse_run(state["values"])
    record = {
        "label": label,
        "input": message,
        "thread_id": report["thread_id"],
        "run_id": run["run_id"],
        "status": completed["status"],
        **parsed,
    }
    record["langsmith"] = await asyncio.to_thread(
        remote_trace, run["run_id"], parsed["completed_model_calls"]
    )
    after = snapshot(options.database, report["request_year"])
    record["business_data_changed"] = business_signature(before) != business_signature(
        after
    )
    record["confirmation_count_before"] = len(before["confirmations"])
    record["confirmation_count_after"] = len(after["confirmations"])
    report["turns"].append(record)
    report["latest_state"] = after
    for output in record["tool_results"]:
        value = output["output"]
        data = value.get("data", {}) if isinstance(value, dict) else {}
        if (
            isinstance(data, dict)
            and data.get("status") == "confirmation_required"
            and data.get("operation") == "request_leave"
            and data.get("arguments", {}).get("start_date")
            == report["requested_dates"][0]
        ):
            report["proposal"] = data
    save(report, options.report)
    print(label + ": " + record["final_response"], flush=True)
    return record


def api(options, method, path, payload=None, user="ahmed"):
    with httpx.Client(base_url=options.fastapi_url, timeout=30) as client:
        response = client.request(
            method, path, json=payload, headers={"X-Demo-User": user}
        )
        return {"http_status": response.status_code, "body": response.json()}


def check_proposal_binding(report, options):
    proposal = report.get("proposal")
    if not proposal:
        raise DemoError(
            "Agent has not produced a valid leave proposal; no confirmation is possible."
        )
    rows = [
        r
        for r in snapshot(options.database, report["request_year"])["confirmations"]
        if r["id"] == proposal["confirmation_id"]
    ]
    if len(rows) != 1 or rows[0]["actor_id"] != "ahmed":
        raise DemoError(
            "Agent Server proposal does not match the isolated database/owner."
        )
    remote = api(options, "GET", "/confirmations/" + proposal["confirmation_id"])
    if (
        remote["http_status"] != 200
        or remote["body"]["data"]["arguments"] != proposal["arguments"]
    ):
        raise DemoError("FastAPI is not using the same proposal/database.")
    return remote


def verify_negative_after_approval(report, options):
    """Repeat only the controlled backend rejection, with no additional LLM calls."""
    args = report.get("negative", {}).get("arguments")
    if not args:
        return
    before = snapshot(options.database, report["request_year"])
    count = api(
        options, "POST", "/operations/calculate_leave_days", {"arguments": args}
    )
    actual_days = count.get("body", {}).get("data", {}).get("working_days")
    remaining = before["balances"][str(report["request_year"])]["remaining_days"]
    if actual_days is None or actual_days <= remaining:
        report["negative"]["post_approval_backend_check"] = {
            "status": "NOT RUN",
            "reason": "Range is not demonstrably over the current requested-year balance.",
        }
        return
    response = api(options, "POST", "/operations/request_leave", {"arguments": args})
    after = snapshot(options.database, report["request_year"])
    report["negative"]["post_approval_backend_check"] = {
        "channel": "Independent FastAPI service check, not an agent tool call",
        "working_days": actual_days,
        "remaining_days_before": remaining,
        "response": response,
        "business_data_unchanged": business_signature(before)
        == business_signature(after),
        "no_new_proposal": len(before["confirmations"]) == len(after["confirmations"]),
    }


def approval_phrase(label, cid):
    phrase = "CONFIRM " + cid
    print(
        label + " requires explicit developer approval. Type exactly: " + phrase,
        flush=True,
    )
    try:
        answer = input("> ").strip()
    except EOFError:
        raise DemoError("No developer authorization received; action not executed.")
    if answer != phrase:
        raise DemoError("Authorization phrase did not match; action not executed.")
    return {
        "approved_at": utc(),
        "mechanism": "Explicit proposal-specific local console confirmation",
        "proposal_id": cid,
    }


async def live(options):
    load_dotenv(ROOT / ".env")
    if options.report.exists():
        if not options.resume:
            raise DemoError(
                "Results already exist; choose --resume or another --report. Never reset a demo silently."
            )
        report = json.loads(options.report.read_text())
    else:
        if options.resume:
            raise DemoError("No saved workflow to resume.")
        start, end = PLANNED_START, PLANNED_END
        now = datetime.now(
            ZoneInfo(os.getenv("COMPANY_TIMEZONE", "Europe/Berlin"))
        ).date()
        reason = None
        if date.fromisoformat(start) < now:
            d = now + timedelta(days=30)
            while d.weekday() != 0:
                d += timedelta(days=1)
            start, end = str(d), str(d + timedelta(days=4))
            reason = "Original January 2027 range was in the past; selected a future Monday-Friday explicitly."
        year = int(start[:4])
        initial = snapshot(options.database, year)
        report = {
            "workflow_id": uuid.uuid4().hex,
            "phase": "initial",
            "started_at": utc(),
            "request_year": year,
            "requested_dates": [start, end],
            "date_change_reason": reason,
            "isolated_database": str(options.database.resolve()),
            "initial_state": initial,
            "latest_state": initial,
            "turns": [],
            "checks": {
                "identity_mapping": "PASS",
                "conversation_memory": "FAIL: existing Studio hook clears previous turns; no application fix applied",
                "developer_submission_authorization": "NOT RECEIVED",
                "developer_manager_authorization": "NOT RECEIVED",
            },
        }
    client = get_client(url=options.agent_url)
    if not report.get("thread_id"):
        thread = await client.threads.create()
        report["thread_id"] = thread["thread_id"]
        save(report, options.report)
    start, end = report["requested_dates"]
    eid = report["initial_state"]["employee"]["id"]
    if not options.resume:
        first = await turn(
            client,
            report,
            options,
            "incomplete_request",
            "I want to take some annual leave next month.",
        )
        report["checks"]["missing_information_no_proposal"] = (
            "PASS"
            if not first["business_data_changed"]
            and first["confirmation_count_before"] == first["confirmation_count_after"]
            else "FAIL"
        )
        await turn(
            client,
            report,
            options,
            "exact_dates",
            f"I want to take leave from {date.fromisoformat(start):%B %d, %Y} to {date.fromisoformat(end):%B %d, %Y}.",
        )
        args = {"employee_id": eid, "start_date": start, "end_date": end}
        report["backend_read_checks"] = {}
        for operation, values in [
            ("get_leave_balance", {"employee_id": eid}),
            ("calculate_leave_days", args),
            ("check_leave_overlap", args),
            ("check_leave_eligibility", {"employee_id": eid}),
            ("get_leave_history", {"employee_id": eid, "year": report["request_year"]}),
        ]:
            report["backend_read_checks"][operation] = api(
                options, "POST", "/operations/" + operation, {"arguments": values}
            )
        await turn(
            client,
            report,
            options,
            "read_only_validations",
            f'For my annual leave from {start} to {end}, verify eligibility, working days excluding holidays/weekends and overlap, and show my current-year balance and {report["request_year"]} leave history. Read-only checks only; do not create or modify a request.',
        )
        memory = await turn(
            client,
            report,
            options,
            "context_probe",
            "Which exact leave dates did I just request? Do not submit or change anything.",
        )
        report["checks"]["context_probe_dates_present"] = all(
            d in str(memory["final_response"]) for d in [start, end]
        )
        # Construct an explicit non-overlapping range exceeding the actual allowance.
        d = date(report["request_year"], 3, 1)
        if d <= date.fromisoformat(end):
            d = date.fromisoformat(end) + timedelta(days=30)
        while d.weekday() in report["initial_state"]["weekends"]:
            d += timedelta(days=1)
        negative_start = d
        count = 0
        required = max(
            40,
            report["initial_state"]["balances"][str(report["request_year"])][
                "remaining_days"
            ]
            + 10,
        )
        holidays = {h["day"] for h in report["initial_state"]["holidays"]}
        while count < required:
            if (
                d.weekday() not in report["initial_state"]["weekends"]
                and str(d) not in holidays
            ):
                count += 1
            if count < required:
                d += timedelta(days=1)
        if d.year != negative_start.year:
            raise DemoError(
                "Negative range crosses years; supply a manual controlled scenario instead."
            )
        negative_args = {
            "employee_id": eid,
            "start_date": str(negative_start),
            "end_date": str(d),
        }
        report["negative"] = {
            "arguments": negative_args,
            "intended_working_days": required,
            "actual_days_check": api(
                options,
                "POST",
                "/operations/calculate_leave_days",
                {"arguments": negative_args},
            ),
        }
        before = snapshot(options.database, report["request_year"])
        await turn(
            client,
            report,
            options,
            "over_balance_request",
            f"I want to request {required} working days of annual leave from {negative_start} to {d}. Please use the backend to validate this request; do not bypass its balance rules.",
        )
        # Independently verify the backend if the model refused before submitting.
        report["negative"]["independent_backend_check"] = api(
            options, "POST", "/operations/request_leave", {"arguments": negative_args}
        )
        after = snapshot(options.database, report["request_year"])
        report["negative"]["business_data_unchanged"] = business_signature(
            before
        ) == business_signature(after)
        report["negative"]["no_new_proposal"] = len(before["confirmations"]) == len(
            after["confirmations"]
        )
        report["checks"]["negative_backend_rejection"] = (
            "PASS"
            if report["negative"]["independent_backend_check"]["http_status"] == 422
            and report["negative"]["no_new_proposal"]
            else "FAIL"
        )
        if report.get("proposal"):
            report["proposal_binding"] = check_proposal_binding(report, options)
            report["checks"]["no_premature_business_change"] = (
                "PASS"
                if business_signature(report["initial_state"])
                == business_signature(after)
                else "FAIL"
            )
            report["phase"] = "awaiting_submission_authorization"
        else:
            report["phase"] = "no_valid_proposal_created"
    if options.confirm_submission and report.get("submission"):
        raise DemoError(
            "Submission already recorded; use its receipt. Do not replay a completed stage as a new action."
        )
    if options.confirm_submission:
        binding = check_proposal_binding(report, options)
        cid = report["proposal"]["confirmation_id"]
        authorization = approval_phrase(
            "Submit pending leave (not manager approval)", cid
        )
        before = snapshot(options.database, report["request_year"])
        response = api(options, "POST", "/confirmations/" + cid, {"confirm": True})
        if response["http_status"] != 200:
            raise DemoError("Submission confirmation rejected; state not bypassed.")
        after = snapshot(options.database, report["request_year"])
        replay = api(options, "POST", "/confirmations/" + cid, {"confirm": True})
        replay_state = snapshot(options.database, report["request_year"])
        report["submission"] = {
            "authorization": authorization,
            "response": response,
            "replay_response": replay,
            "replay_business_unchanged": business_signature(after)
            == business_signature(replay_state),
            "before": before,
            "after": after,
        }
        report["checks"]["developer_submission_authorization"] = "RECEIVED"
        report["phase"] = "submitted_pending_manager"
    if options.prepare_manager_approval:
        submission = (
            report.get("submission", {})
            .get("response", {})
            .get("body", {})
            .get("data", {})
        )
        if not submission.get("request_id"):
            raise DemoError("Submission has not been confirmed.")
        managers = report["initial_state"]["manager"]
        if len(managers) != 1 or "manager" not in json.loads(managers[0]["roles"]):
            raise DemoError("Assigned manager identity not verified.")
        manager = managers[0]["demo_user"]
        response = api(
            options,
            "POST",
            "/operations/review_leave_request",
            {
                "arguments": {
                    "request_id": submission["request_id"],
                    "decision": "approve",
                }
            },
            manager,
        )
        if response["http_status"] != 200:
            raise DemoError("Manager approval proposal rejected by backend.")
        report["manager_approval"] = {
            "manager_identity": managers[0],
            "proposal": response["body"]["data"],
            "status": "awaiting_explicit_developer_authorization",
        }
        report["phase"] = "awaiting_manager_authorization"
    if (
        options.confirm_manager_approval
        and report.get("manager_approval", {}).get("status") == "approved"
    ):
        raise DemoError(
            "Manager approval already recorded; do not re-run as a new approval."
        )
    if options.confirm_manager_approval:
        manager = report["manager_approval"]
        cid = manager["proposal"]["confirmation_id"]
        authorization = approval_phrase(
            "Assigned manager approval and requested-year leave deduction", cid
        )
        before = snapshot(options.database, report["request_year"])
        response = api(
            options,
            "POST",
            "/confirmations/" + cid,
            {"confirm": True},
            manager["manager_identity"]["demo_user"],
        )
        if response["http_status"] != 200:
            raise DemoError("Manager confirmation rejected by backend.")
        after = snapshot(options.database, report["request_year"])
        replay = api(
            options,
            "POST",
            "/confirmations/" + cid,
            {"confirm": True},
            manager["manager_identity"]["demo_user"],
        )
        manager.update(
            {
                "authorization": authorization,
                "confirmation_response": response,
                "replay_response": replay,
                "replay_business_unchanged": business_signature(after)
                == business_signature(
                    snapshot(options.database, report["request_year"])
                ),
                "before": before,
                "after": after,
                "status": "approved",
            }
        )
        report["checks"]["developer_manager_authorization"] = "RECEIVED"
        report["phase"] = "manager_approved"
    if options.post_check:
        await turn(
            client,
            report,
            options,
            "post_operation_status",
            "Show me my updated leave balance and the status of my latest leave request.",
        )
        # Independently fetch actual requested-year history if the model cannot remember the year.
        report["post_operation_history"] = api(
            options,
            "POST",
            "/operations/get_leave_history",
            {"arguments": {"employee_id": eid, "year": report["request_year"]}},
        )
    if (
        options.post_check
        and report.get("manager_approval", {}).get("status") == "approved"
    ):
        verify_negative_after_approval(report, options)
    if options.interactive:
        while True:
            try:
                message = input("Same-thread message (blank to stop): ").strip()
            except EOFError:
                break
            if not message:
                break
            await turn(
                client,
                report,
                options,
                "interactive_" + str(len(report["turns"]) + 1),
                message,
            )
    report["latest_state"] = snapshot(options.database, report["request_year"])
    report["checks"]["all_remote_traces_found"] = (
        "PASS"
        if all(t["langsmith"].get("status") == "PASS" for t in report["turns"])
        else "FAIL"
    )
    save(report, options.report)
    print("Phase:", report["phase"])
    print("Thread:", report["thread_id"])
    if report.get("proposal"):
        print("Submission proposal:", report["proposal"]["confirmation_id"])
    print("Completed model calls:", report["total_completed_model_calls"])
    print("Report:", options.report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--confirm-submission", action="store_true")
    parser.add_argument("--prepare-manager-approval", action="store_true")
    parser.add_argument("--confirm-manager-approval", action="store_true")
    parser.add_argument("--post-check", action="store_true")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--agent-url", default="http://127.0.0.1:2024")
    parser.add_argument("--fastapi-url", default="http://127.0.0.1:8001")
    options = parser.parse_args()
    if not options.live:
        print(
            "PREVIEW ONLY: inspect isolated state → one thread → clarify dates → exact dates/proposal → read-only validations → context probe → controlled over-balance rejection → STOP for explicit submission authorization → STOP separately for manager authorization → same-thread final read check. No model calls or database changes."
        )
        return
    for value in [options.agent_url, options.fastapi_url]:
        parsed = urlparse(value)
        try:
            allowed = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            allowed = False
        if not allowed or parsed.scheme != "http":
            parser.error("Use loopback HTTP URLs only.")
    try:
        asyncio.run(live(options))
    except DemoError as exc:
        print("Workflow stopped:", str(exc), file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        # Do not echo arbitrary provider/HTTP errors, which may carry sensitive data.
        print(
            "Workflow stopped:",
            type(exc).__name__,
            "— inspect the saved report and local configuration. No authorization bypass attempted.",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
