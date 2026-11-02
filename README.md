# Company AI Agent

An educational Python 3.11+ extension of the original HR Agent. One configurable
OpenAI model and one LangChain `create_agent` handle 60 business operations across
nine modules, using deterministic Python services and one local SQLite database.
All seeded people, customer orders, payroll and financial records are fictional.
The existing HR chat page and employee lookup endpoint are preserved.

## Architecture

```text
Existing browser / HTTP client
  → FastAPI (application-selected demo identity)
  → one Company AI Agent (model + system prompt + 11 reusable tools)
  → typed, authorized Python services (60 operations)
  → SQLite → tool result → model's final answer

Write operation → immutable confirmation proposal → human HTTP confirmation
               → permissions/rules rechecked → atomic database transaction
```

`create_agent` supplies the LangGraph model/tool loop. There is no custom graph,
checkpoint, conversation memory, multi-agent system, RAG, evaluation framework,
tracing integration, external database, payment execution or account disabling.
The LLM chooses tools and arguments; Python enforces the rules.

## Install and run

```bash
cd /Users/sabahy/Documents/Codex/2026-11-01/files-pasted-by-the-user-you/outputs/hr-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Only if .env does not already exist:
cp -n .env.example .env
# Edit .env manually to configure your own OPENAI_API_KEY.
python database.py
uvicorn main:app --reload --host 127.0.0.1
```

Open http://127.0.0.1:8000/. The existing UI defaults to Ahmed, supports independent
chat questions, and has not been extended with identity or confirmation controls.
Use an HTTP client for the new modules, user selection and human confirmations.
The original employee questions continue to work.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required only for real `/chat` model calls. Keep in local `.env`. |
| `OPENAI_MODEL` | Model name; defaults to `gpt-4.1-mini`. |
| `COMPANY_TIMEZONE` | Calendar date/schedule timezone; defaults to `Europe/Berlin`. |
| `COMPANY_DB_PATH` | Optional SQLite path; defaults to `data/company.db`. |

Existing process environment variables take precedence over `.env`. SQLite, the
virtual environment and all real credentials are ignored by Git.

## Database initialization

`python database.py` creates tables and imports the original three employees from
`employees.json`, adding four fictional colleagues and nine local demo identities.
Startup also runs initialization. Seeding is transactional and idempotent: a
`seed_version` setting prevents overwriting existing data. Fixtures use dates
relative to the company's local date **when first initialized**, not on every run.
For a fresh demo, select a new `COMPANY_DB_PATH`; existing databases are preserved.
`employees.json` is now a migration/seed source, not the live employee store.

Tables (28): `settings`, `departments`, `employees`, `users`, `policies`, `holidays`,
`leave_balances`, `leave_requests`, `attendance`, `shifts`, `timesheets`, `requests`,
`tickets`, `courses`, `enrollments`, `payslips`, `inventory_items`, `assets`,
`software`, `licenses`, `purchase_orders`, `orders`, `invoices`, `budgets`,
`projects`, `project_members`, `tasks`, `confirmations`.

Related pending workflows share `requests` with a typed service-owned JSON payload;
IT, payroll, restricted HR cases and customer complaints share `tickets` with
separate permission checks. Confidential content has no generic read endpoint.

## Demo identity and authorization

This is a **local-only test-user selector, not authentication**. Bind to loopback.
The HTTP caller explicitly selects `X-Demo-User`; the default is `ahmed` to preserve
the existing UI and API. The server loads the employee/customer ID and roles from
SQLite and carries identity through a request-local context variable into tools.
No operation accepts an actor, role, permission or `confirmed` argument. Natural
language cannot change the selected identity. Unknown selectors return HTTP 401.

| `X-Demo-User` | Stable identity | Roles |
| --- | --- | --- |
| `ahmed` | E001 | employee |
| `sara` | E002 | employee, HR |
| `lina` | E003 | employee, finance, payroll |
| `nadia` | E004 | employee, assigned Engineering manager |
| `youssef` | E005 | employee, HR, assigned HR manager |
| `mona` | E006 | employee, finance, payroll, assigned Finance manager |
| `new-starter` | E007 | employee, not yet leave eligible |
| `customer-1` | C001 | customer |
| `customer-2` | C002 | customer |

Self-service confidential information is restricted to the matching employee.
HR may read designated leave/profile-support records; only self/payroll may read
payslips. Only the assigned manager may review an employee's leave; managers may
not approve their own leave. Finance reads require a finance role, except a
manager may check their own department budget. Customers access only their own
orders/tickets; project access requires membership. Directory tools expose only
IDs, names, departments and roles. Selecting another identity is possible for
local testing and must never be treated as secure login or deployed publicly.

## HTTP endpoints

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/` | Existing chat page, unchanged |
| GET | `/employees/{name}` | Compatible employee lookup, now includes `employee_id` |
| POST | `/chat` | `{ "message": "..." }` → answer and pending confirmation references |
| GET | `/demo/users` | Explicit fictional test identities and roles |
| GET | `/operations` | All 60 operation names, descriptions and Pydantic argument schemas |
| POST | `/operations/{operation}` | Typed arguments → shared service result/proposal |
| GET | `/confirmations/{id}` | Owner-only exact proposed arguments and status |
| POST | `/confirmations/{id}` | Owner's `{ "confirm": true/false }` decision |

Business responses use `{ "ok": true, "data": ... }` or
`{ "ok": false, "error": "...", "code": "..." }` (optional fields may be null).
Legacy employee success returns directory fields directly; chat retains `answer`
and adds `confirmations`. Errors use HTTP 401/403/404/409/422; absent API key uses
503 and model failures use 502 without returning provider errors or credentials.
An ineligible eligibility check may return HTTP 200 with `eligible: false`; that
is a successful check, not approval. FastAPI docs/schema routes remain disabled.

## Available tools and modules

There are **11 LangChain tools**, not 60 separate agents/tools:

* `get_employee(name)` preserves natural-language employee lookup and stable IDs.
* `describe_operation(operation)` returns the exact argument schema.
* Nine reusable tools accept `operation` and `arguments`: `hr_operations`,
  `attendance_operations`, `employees_operations`, `payroll_operations`,
  `it_operations`, `inventory_operations`, `customers_operations`,
  `finance_operations`, `projects_operations`.

Each module tool dispatches only to its own allowlisted operations. It calls the
same service function as `/operations/{operation}`; neither path duplicates rules.
The model is instructed to inspect a schema and ask for missing required inputs.
See [SCENARIOS.md](SCENARIOS.md) for all 60 operation names, scenarios, rules and data.

| Module | Scenarios | Coverage |
| --- | --- | --- |
| Leave | 01–12 | Balance, requests, cancellation, modification, overlap, coverage, working-day calculation, manager review, history, carryover projection, eligibility, policies |
| Attendance | 13–20 | Records, late arrivals, missing check-out, overtime, timesheet validation, shift swap, remote work, check-in correction |
| Employees | 21–30 | Directory, profile fields, transfer, manager/team lookup, onboarding/offboarding, probation, document request, training eligibility |
| Payroll / HR support | 31–35 | Fictional payslips, payroll ticket, reimbursement request, restricted HR case, policy search |
| IT | 36–40 | Support tickets/status, software/device requests, ownership-scoped warranty |
| Inventory | 41–45 | Stock, pending requests, low stock, quantity/limit checks, known restock dates |
| Customers | 46–50 | Order tracking, returns, return eligibility, pre-shipment address update, escalation |
| Finance | 51–55 | Invoices, duplicate checks, department budget, pending purchase approvals, overdue invoices |
| Projects | 56–60 | Tasks, overdue work, potential deadline conflicts, controlled transitions, computed progress |

## Examples

Directory (works without an OpenAI key):

```bash
curl http://127.0.0.1:8000/employees/Ahmed
```

Agent (uses real model calls):

```bash
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' -H 'X-Demo-User: ahmed' \
  -d '{"message":"How many vacation days do I have left?"}'
```

Deterministic service call (no LLM cost):

```bash
curl http://127.0.0.1:8000/operations/get_leave_balance \
  -H 'Content-Type: application/json' -H 'X-Demo-User: ahmed' \
  -d '{"arguments":{"employee_id":"E001"}}'

curl http://127.0.0.1:8000/operations/get_invoice_status \
  -H 'Content-Type: application/json' -H 'X-Demo-User: lina' \
  -d '{"arguments":{"invoice_id":"INV-100"}}'

curl http://127.0.0.1:8000/operations/check_return_eligibility \
  -H 'Content-Type: application/json' -H 'X-Demo-User: customer-1' \
  -d '{"arguments":{"order_id":"ORD-1"}}'
```

### Propose, inspect and confirm a change

```bash
curl http://127.0.0.1:8000/operations/update_employee_profile \
  -H 'Content-Type: application/json' -H 'X-Demo-User: ahmed' \
  -d '{"arguments":{"employee_id":"E001","field":"preferred_name","value":"Ahmed Demo"}}'

# Copy the confirmation_id from the response, inspect the exact proposal:
curl http://127.0.0.1:8000/confirmations/CONFIRMATION_ID \
  -H 'X-Demo-User: ahmed'

# Only the human caller confirms. Use false to cancel instead.
curl http://127.0.0.1:8000/confirmations/CONFIRMATION_ID \
  -H 'Content-Type: application/json' -H 'X-Demo-User: ahmed' \
  -d '{"confirm":true}'
```

No business change is made when a proposal is returned. Every write operation
first runs its real validation inside a rolled-back SQLite savepoint. Valid
proposals bind the actor, operation and exact validated arguments, expire after
15 minutes, and are not modifiable by tools. Confirming rechecks current rules
inside `BEGIN IMMEDIATE`; failed validation rolls everything back. Replaying a
completed confirmation returns its receipt without executing the change again.
The LLM has no confirmation tool. A chat message saying "yes" cannot confirm.

For leave: request as Ahmed; confirm the proposal as Ahmed; take the resulting
leave `request_id`; propose `review_leave_request` with decision `approve` as
Nadia; inspect and confirm that second proposal **as Nadia**. Leave usage is only
deducted on manager approval. Other request types are queued for human processing,
not silently approved by the model.

## Configured demo rules

* Default annual allowance 30 working days, eligibility after 90 days of active
  employment, Saturday/Sunday weekends, configured holiday dates. Inclusive
  date ranges; no cross-year request (submit one per year), zero-day booking,
  past booking or overlapping pending/approved leave. Cancellation is allowed
  before the start date has passed; approved modifications restore the original
  deduction and require reapproval. Team minimum coverage is checked per day.
* Carryover is a projection of at most 5 unused days with March 31 expiry; it does
  **not** automatically transfer or credit days. Probation uses 180 calendar days.
* Default work schedule 09:00–17:00; assigned shifts override start/end times for
  attendance checks. Ten-minute late grace; overtime at most 4 hours/day and no
  more than recorded extra hours. Corrections do not overwrite original records.
  Remote-work requests require assigned working days and reserve one of 8 monthly
  request slots (pending/approved requests count).
* Inventory requests check positive integer quantity, current stock and per-item
  limit. Pending inventory/device requests do **not** reserve or deduct stock;
  human fulfillment must recheck availability. Software requests check remaining
  licenses and other pending reservations, without assigning licenses.
* Standard customer return window: 14 days after delivery, inclusive. Fictional
  `ORD-OLD` has a configured 30-day exception. Shipment blocks address changes.
* Amounts are positive EGP values, at most two decimal places; storage/calculation
  uses integer cents. Reimbursements require supported category/receipt and at
  most 5,000 EGP. Confirmed pending purchase-approval requests reserve department
  budget atomically but do not pay invoices or transfer money.
* Task transitions: pending → in_progress/completed, in_progress → completed;
  completed tasks cannot be reopened in this demo. Deadline conflicts are a
  scheduling signal only and make no capability/employment decisions.

Policies live in SQLite `settings`, `policies`, `holidays`, department staffing
fields, shifts, and item thresholds. Change fixtures for a fresh demo or maintain
configuration directly as a trusted developer; there is no policy-administration
API. Event timestamps are UTC; dates and clock-time comparisons use the configured
company-local calendar. No laws or real company policies are implied.

## Verification

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m pip check
```

Tests use fresh temporary SQLite databases and no paid model calls. They cover all
60 operations plus API/lookup regression, authorization failures, strict argument
validation, business-data rollback before confirmation, confirmation ownership,
expiry, replay/concurrency, budget revalidation, and an offline LangGraph/tool
integration check. Fake-model tests verify wiring, **not** natural-language model
quality. No automated LLM scoring or evaluator is included.

## Files

* `agent.py`: one model, system prompt and cached `create_agent`.
* `main.py`: existing routes plus generic operation and human-confirmation routes.
* `database.py`: schema, connections, company date/UTC helpers and initialization.
* `models.py`: Pydantic HTTP request/response models.
* `services/common.py`: typed operation registry, validation, identity, transactions
  and confirmations; eight domain modules hold actual business logic.
* `tools/company_tools.py`: employee lookup, schema discovery and reusable tools.
* `data/seed.py`: one-time fictional fixtures; `employees.json`: original seed data.
* `tests/test_business.py`: offline engineering verification.
* `index.html`: preserved existing frontend; no new frontend is implemented.
* `.env.example`, `.gitignore`, `requirements.txt`: configuration/dependencies.
* `SCENARIOS.md`: implementation traceability for all 60 scenarios.

## Known limitations

This is a single-process educational local application, not an authenticated
enterprise system. Anyone able to call the local API can choose a demo identity;
SQLite files are not encrypted. Keep it on loopback and use fictional data only.
Pending workflows other than leave review are queues/checklists for humans;
fulfillment, payments, actual document generation, course enrollment, account
changes and notification delivery are intentionally outside these scenarios.
Offboarding records an unapproved departure date as null for HR to supply later.
No generic confidential ticket-reading endpoint is exposed. There is no new
frontend/identity picker/confirmation UI, conversation memory, rate limiter,
public deployment configuration, schema migration framework or external holiday
feed. Policies and date/time behavior are demo rules, not legal/payroll guidance.

### Latest verification run

69 offline engineering tests passed. One read-only live `/chat` request also
passed, using 3 OpenAI model calls. The model initially supplied an unsupported
`leave_type` argument; strict backend validation rejected it. The model retried
with `employee_id` alone, retrieved the real balance, and returned 30 days for
Ahmed. Both tool results were observed in subsequent model input. This is one
live smoke test, not live verification of all 60 natural-language scenarios.

## Tool Calling and Argument Validation

The existing 11 tools still cover all 60 operations. Names and canonical HTTP
arguments are preserved. Each module tool now exposes an enum of its own actions,
a generated signature catalog, read/write markers, when-to-use guidance and
important distinctions (stock checks versus requests, reimbursement versus
purchase approval, invoice status versus duplicate detection).

`operation_schemas.py` supplies shared `Field` descriptions/constraints and a
Pydantic base model. Actual service signatures supply names and defaults; the
registry builds each operation schema once. `describe_operation` and
`GET /operations` expose that same schema, required/optional field lists,
authorization notes and confirmation requirements. All 60 current business
operations use signature-derived fields. `get_leave_balance(employee_id, year=None)` now has one optional business argument: omit/null for the current year, or supply an explicit year from 1900 through 2200. Authorization is unchanged.
Dates remain ISO strings for API compatibility but are parsed/validated as real
calendar values before dispatch. Positive finite amounts/counts, exact money
precision, IDs, clock/month formats, date ordering, enums and unexpected fields
are validated before a service function runs. Existing business rules still
validate eligibility, current balances, policies, stock, ownership and transitions.

Missing inputs return structured `missing_fields`, `errors`,
`clarification_required` and `next_step`, without echoing input values or traces.
The model is told to ask a concise question instead of inventing data. Trusted
self identity is included in application context and metadata/error hints: a
missing tool `employee_id` must not turn into an unnecessary user-ID question.
Another target is never silently rebound to self; authorization remains separate.
Ambiguous employee names are rejected rather than arbitrarily matched.

For natural-language chat, month/day without an explicit year always requires
clarification. `tools/input_context.py` checks calendar arguments against the
original request before dispatch. It supports explicit four-digit years (including
Arabic digits), today/tomorrow/yesterday, current week/month ranges and current
year. Current week means Monday–Sunday. Other ambiguous relative expressions
require clarification. This guard is not a general intent router or a complete
provenance parser. Direct HTTP operations already supply canonical dates and use
normal schemas, permissions and confirmations without this natural-language guard.

FastAPI and default Studio chat remain independent: after a clarification, restate the full request. Opt-in Studio memory supports bounded follow-ups as documented below.
A structurally incomplete or invalid call does not execute a business service or create a
confirmation proposal. A complete, authorized write only produces a proposal;
no model tool can execute human confirmation. Existing database tables and
business endpoints are preserved.

Run deterministic tests and regenerate the actual schema audit:

```bash
python -m unittest discover -s tests -v
python scripts/generate_tool_audit.py
```

The optional live script defaults to listing cases and makes **zero API calls**.
`--live` requires explicit case selection, a real key and a model-call cap. Each
case uses a temporary fictional database, records actual calls/arguments/results
and never confirms changes:

```bash
python scripts/live_tool_checks.py
python scripts/live_tool_checks.py --live \
  --cases complete_leave,missing_leave_dates,invalid_quantity \
  --max-model-calls 10 --output live-local-results.json
```

See [TOOL_AUDIT.md](TOOL_AUDIT.md) for every tool description, all 60 required/optional
contracts, schema constraints, observed failures and limitations. Full live traces
are in [LIVE_TOOL_CHECKS.json](LIVE_TOOL_CHECKS.json). Offline wiring tests cannot
prove real LLM clarification behavior; live smoke checks are separate and do not
claim all-60 coverage or consistent reliability. No LLM-as-a-Judge is used.

Latest tool-audit verification: **85 offline tests passed** (the original 69 plus
16 focused tool-contract tests). Live checks used **45 model calls across 27
requests**, including three failed attempts and their targeted retests; all 20
distinct sampled cases have a passing latest result. Earlier failures and complete
responses remain in the report. All live business-data snapshots were unchanged.
This does not establish reliable behavior for every possible prompt or all 60
operations. In particular, permission explanations can still overstate policy;
backend authorization, not prose, remains authoritative.

## LangGraph Studio

Studio is an interactive graph/debugging UI for inspecting observable model
messages, selected tools, operations, arguments, ToolMessages and final responses.
It does not reveal hidden model reasoning. This integration exports the **same
`create_agent` implementation** through an async factory; it adds no second agent,
custom business graph, evaluator, frontend or alternative authorization system.

The tested local stack is `langgraph-cli[inmem]==0.4.40`, Agent Server 0.17.0 and
in-memory runtime 0.37.0. The CLI extra is in `requirements.txt`; Python 3.11+ is
required and `langgraph dev` needs no Docker. Official references:
[local server](https://docs.langchain.com/oss/python/langgraph/local-server),
[CLI](https://docs.langchain.com/langsmith/cli),
[graph factories](https://docs.langchain.com/langsmith/graph-rebuild).

`langgraph.json` registers `company_agent` at `./studio_graph.py:build_graph`, loads
`.env`, and installs a loopback-only ASGI gate. The factory initializes the same
SQLite services without FastAPI startup, then calls `get_agent(studio=True)`.
There is still one shared agent construction site. Studio middleware binds the
fixed environment-selected fictional user around every sync/async tool call and
injects its trusted context into model requests. Client input/config/runtime
context cannot set roles or identity. Submitted system/AI/tool messages are removed at the start of each turn. Old human history is also removed by default; explicit Studio conversation mode instead retains a bounded, signed human ledger as documented below.

Studio demo mode is **disabled by default**. Explicitly opt in locally:

```bash
source .venv/bin/activate
pip install -r requirements.txt
export STUDIO_DEMO_ENABLED=1
export STUDIO_DEMO_USER=ahmed
export LANGSMITH_TRACING=false
export LANGCHAIN_TRACING_V2=false
# Recommended disposable demo; omit to reuse the ordinary business database.
export COMPANY_DB_PATH="$PWD/data/studio-demo.db"
langgraph dev --host 127.0.0.1 --port 2024
```

Once configured, plain `langgraph dev` uses the same loopback/2024 defaults. Keep
the server local; **no tunnels, public hosts or reverse proxies**. This is a fixed
local test identity, not production authentication. Changing Studio configuration,
claiming “I am payroll”, or supplying another employee ID does not grant access.
The loopback middleware also rejects non-loopback client/server addresses.

Open [Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024),
select `company_agent`, add a human/user message and Submit. Expand `model` to see
its tool-call arguments, `tools` for operation output/field errors/denials, and the
final `model` for its answer. The Thread selector opens recorded runs. Local graph
execution was verified without a LangSmith API key; a missing-key banner or optional
cloud Trace/login feature does not mean local tools are unavailable. Tracing stays
off; use fictional data only in the hosted Studio browser UI.

FastAPI is unchanged and remains independently runnable:

```bash
uvicorn main:app --reload --host 127.0.0.1
```

Both use the same `COMPANY_DB_PATH` resolution. If demonstrating human HTTP
confirmation, start FastAPI with Studio's identical demo database path (use port
8001 if the existing app is already on 8000). Studio only reads or creates pending
proposals: it has no confirmation endpoint/tool, and “yes, approve it” cannot
commit one. Inspect and confirm a real proposal through the existing authorized
FastAPI workflow; business rules are rechecked and manager approval stays separate.
Verification used an isolated demo DB; the user's original DB was not reset.

```bash
python demo_studio.py                 # Lists five cases; no paid calls.
python demo_studio.py --live          # Opt in to five real server requests.
python -m unittest discover -s tests -v
```

See [STUDIO_DEMO.md](STUDIO_DEMO.md) for the five manager scenarios, exact arguments,
UI walkthrough, confirmation boundary and startup troubleshooting. Actual inputs,
outputs and failed attempts are retained in [STUDIO_RESULTS.json](STUDIO_RESULTS.json).
Six live requests (five plus one retry) completed 8 model calls; four scenarios
passed. The payslip attempts disclosed no data but did not call the backend, so
that live boundary check is explicitly unverified/failed; deterministic tests
verify the rejection at the real service/tool boundary. No claim of universal
model reliability is made. The ignored `.langgraph_api/` directory holds local dev
thread/checkpoint metadata, independently of business SQLite data.

Final Studio regression result: **96 offline tests passed**. The adapter also appends a real backend proposal receipt to final prose when the model omits its ID, without creating or confirming any action.


## Opt-in Studio conversation memory and year-aware balances

`STUDIO_CONVERSATION_MEMORY_ENABLED=false` is the default. Ordinary FastAPI chat
and Studio with the flag disabled still treat every request independently.
Enable it only on the loopback fictional Studio demo:

```bash
source .venv/bin/activate
STUDIO_DEMO_ENABLED=1 STUDIO_DEMO_USER=ahmed \
STUDIO_CONVERSATION_MEMORY_ENABLED=true \
COMPANY_DB_PATH="$PWD/data/leave-workflow-demo.db" \
LANGSMITH_TRACING=true LANGCHAIN_TRACING_V2=true \
LANGSMITH_PROJECT=company-agent-demo \
langgraph dev --host 127.0.0.1 --port 2024 --no-browser --no-reload
```

Start a **new thread** after restarting the server. Within one thread the adapter
retains at most **8 previous human messages**, plus the new message, with a
**4,000-character total budget including the new message**. Whole oldest messages
are discarded rather than truncating dates. A new message exceeding 4,000
characters is rejected in memory mode. Only human context is remembered; prior
assistant and tool messages are removed at each turn. Current-turn model/tool
execution proceeds normally.

The human ledger is stored in existing LangGraph checkpoint state, omitted from
the graph input schema, and authenticated with a process-local HMAC bound to the
thread and fixed server identity. Incoming combined message history is never
trusted as prior context. Forged or edited ledgers fail closed; copying a ledger
to another thread or identity fails verification. The signing key is ephemeral,
so memory cannot be resumed across server restarts: start a fresh thread. This
local single-process demo is not production authentication. Access to a thread ID
alone grants no company permissions; all tools still bind STUDIO_DEMO_USER and
backend authorization, ownership, confirmation expiry and replay checks apply.
Do not expose the Agent Server/state-edit endpoints publicly. Legitimate old
checkpoints can replay old user intent within the same thread; remembered intent
never proves that a mutation occurred or grants authority.

Memory is disabled by default to preserve independent-turn compatibility and
avoid unexpected retention of user content. Checkpoint/run history can outlive
the bounded model context; the limit is not a storage deletion or privacy policy.
Prior genuine user messages can clarify dates and quantities but cannot prove
identity, permission, approvals or balances. These facts require fresh backend
calls. Conflicting or unrelated years require clarification. The year guard uses
a conservative English/limited Arabic reference heuristic, not a general language
understanding engine: a new unrelated request must supply its own year. Newer
explicit corrections replace older years rather than unioning all history.

The existing `get_leave_balance` operation now accepts:

```python
get_leave_balance(employee_id: str, year: int | None = None)
```

Omitted/null year selects the current company-local year. An explicit integer
1900–2200 selects that year's backend ledger. Unexpected arguments, strings,
booleans and out-of-range years are rejected by the centralized strict schema.
Self/HR authorization remains unchanged. No new tool, endpoint, business table,
memory database or dependency was introduced.

```bash
# Preview: no paid calls or data changes
python demo_memory_fix.py
# Real six-turn conversation, thread-isolation check and identity-spoof check
python demo_memory_fix.py --live
# Offline regressions, keep fake-model traces out of LangSmith
LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false python -m unittest discover -s tests -v
```

The live script preserves evidence and refuses to overwrite an existing
MEMORY_FIX_RESULTS.json. Archive that file before a deliberate rerun. It never
confirms or approves anything. The existing isolated January 2027 request is
already approved: a repeated request must be rejected for overlap, and the
backend should return the actual 25-day 2027 balance. See MEMORY_FIX_RESULTS.md
for actual inputs, outputs, tool arguments, failures, retests and trace links.
