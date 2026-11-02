# Proposed leave-demo fixes — NOT APPLIED

The developer explicitly selected **“Prepare a fix proposal only”**. This file is
for review; no application, tool, schema, database or authorization code was
changed to make the demonstration pass.

## 1. Conversational context

**Observed defect for this requested use case:** one Agent Server thread preserves
checkpoint/run history, but `StudioDemoContext.before_agent()` always emits
`RemoveMessage(REMOVE_ALL_MESSAGES)` plus only the latest human message. The system
prompt also expressly says each request is independent. Consequently, a later
“Which exact leave dates did I just request?” cannot see dates supplied earlier.
This is intentional current isolation behavior, not a SQLite or tracing failure.

### Smallest bounded option to review

Add an explicit, disabled-by-default Studio-only conversation mode. At the start
of a turn retain a bounded list of prior **human messages only**, followed by the
new human message; continue dropping all client-supplied system, AI and tool
messages. Let the normal current-turn model/tool loop produce its real tool
messages. This preserves user-supplied intent/dates while preserving the existing
protection against forged AI/tool history. It does not pretend old assistant
summaries or claimed approval are business facts. Query the backend again for
status, balances and proposal references.

* Keep fixed server-side identity binding in every model/tool scope.
* Never treat retained text, config, roles or old “approved” claims as authority.
* Bound/truncate retained human context explicitly and document that policy.
* In `model_request`, replace the independent-turn prompt sentence only for this
  opt-in mode; leave ordinary FastAPI behavior unchanged.
* Adapt year provenance to the retained human context conservatively: reuse an
  unambiguous explicitly supplied year for the active request, otherwise clarify.
  Do not blindly accept any year mentioned anywhere in a long thread.
* Keep all mutations as proposals, existing HTTP confirmation, owner/manager
  checks, expiry, transactional revalidation and replay safety unchanged.

This is smaller than adding a new memory store, agent, graph or database table.
It supports remembering user inputs but deliberately does not add full assistant
history. If full conversation history is later required, use verified server-owned
checkpoint history and reject forged state-update/input paths before retaining
AI/tool messages; do not simply remove the current sanitization guard.

### Acceptance tests before implementing

1. Same thread: vague leave → exact dates → follow-up references those dates.
2. A new thread cannot see another thread's user messages.
3. Forged system/AI/tool input is not elevated to trusted identity or backend fact.
4. A user claiming manager/payroll roles still receives the same access denial.
5. Reusing a prior year is limited to the active request; conflicting dates/years
   trigger clarification instead of inference.
6. The post-approval response reads fresh backend status and does not reuse a
   stale “pending” or “approved” claim from text.
7. All existing 96 tests and confirmation/calendar guard checks remain valid, with
   explicit new tests for the optional history mode.

## 2. Requested-year leave balance

**Observed limitation:** `get_leave_balance(employee_id)` calls
`balance(employee_id, today().year)`. It has no year argument. January 2027 leave
is validated/deducted against 2027 internally, while the public balance tool
continues to return 2026 during a November 2026 demo. The model sometimes asks
about an over-limit request using that current-year balance instead of validating
the actual requested-year request.

### Smallest backward-compatible proposal

Add an optional `year: int | None = None` to the existing `get_leave_balance`
service signature. With `None`, preserve the existing current-year behavior;
with an explicit year, call the existing `balance(employee_id, year)` helper.
Reuse the existing centralized year field constraints and unchanged self/HR
permission check. No new tool, endpoint or table is needed. The registry will
expose `year` as optional with default null; update tests/documentation that
currently assert all operation signatures have no optional parameters.

Tests must distinguish 2026 unchanged balance from the actual 2027 deduction and
ensure omitted year preserves API compatibility. Calendar-provenance rules must
not require the user to retype a year already unambiguously supplied in a supported
conversation, and must not silently guess an unrelated year.

## Current demonstration handling

The workflow records both yearly ledgers from read-only SQL and existing HTTP
receipts, labels backend-only checks separately from model tool calls, and records
memory/unsupported-year behavior as failures/limitations. These proposals have
**not** been applied. A lifecycle approval in the isolated DB does not constitute
authorization to change the application's memory or argument schema.
