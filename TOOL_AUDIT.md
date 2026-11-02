# Tool calling audit

## Initial findings

The 11 tools and 60 operations existed, with strict signature-derived required fields and safe confirmation/authorization. Module envelopes exposed unconstrained operation strings and generic argument dictionaries. Field descriptions, structural range constraints, explicit authorization metadata and structured clarification errors were missing. Existing backend tests did not establish real-model clarification behavior. No optional business parameters existed. The previous live smoke test had shown an invented extra argument followed by recovery.

## Current inventory and descriptions

Names remain stable for compatibility. There is one agent and 11 tools. Module descriptions are generated from the registry, include signatures and read/write markers, and distinguish neighboring intents. Module envelopes constrain operation to a per-module enum. The generic inner dictionary is validated against the exact operation model before any service call.

### `get_employee`

Look up public employee directory fields and a stable employee_id using an explicit exact name, ignoring case and surrounding whitespace. Read-only; use to resolve named colleagues, not private salary or leave records. If name is absent/partial/ambiguous, ask which employee; never guess a match. Private records require the appropriate module and independent authorization.

### `describe_operation`

Inspect exact required/optional arguments, types, constraints, authorization and confirmation for one operation before dispatch. Read-only metadata, no business changes. Use names in module catalogs; unknown names return the catalog. This does not retrieve employee facts or execute an operation.

### `hr_operations`

Use for annual leave balances, date calculations, eligibility, history, requests and assigned-manager review. For general company policies use payroll_operations/search_hr_policy. Missing leave dates/year or request_id require clarification.
Operations (all listed arguments required unless marked ?):
get_leave_balance(employee_id, year?) [READ ONLY]: Get allowance, approved usage and remaining days for optional year; omitted/null uses current year.
request_leave(employee_id, start_date, end_date) [WRITE PROPOSAL, human confirmation]: Request future annual leave; inclusive dates YYYY-MM-DD. Pending requests do not deduct days.
cancel_leave(request_id) [WRITE PROPOSAL, human confirmation]: Cancel own future pending or approved leave; approved deductions are restored once.
modify_leave(request_id, new_start_date, new_end_date) [WRITE PROPOSAL, human confirmation]: Modify own future leave. Previously approved leave returns to pending for reapproval.
check_leave_overlap(employee_id, start_date, end_date) [READ ONLY]: Check own leave dates against pending and approved bookings.
check_team_leave_conflict(employee_ids, start_date, end_date) [READ ONLY]: HR or assigned managers check simultaneous leave against department minimum staffing.
calculate_leave_days(start_date, end_date, employee_id) [READ ONLY]: Count working days inclusive of endpoints, excluding weekends and company holidays.
review_leave_request(request_id, decision) [WRITE PROPOSAL, human confirmation]: Assigned manager approves or rejects a pending leave request. decision: approve or reject.
get_leave_history(employee_id, year) [READ ONLY]: Get own leave requests and statuses for a calendar year.
calculate_leave_carryover(employee_id, year) [READ ONLY]: Calculate carryover eligibility, limit and next-year expiry. Does not credit a balance.
check_leave_eligibility(employee_id) [READ ONLY]: Check active employment and configured minimum tenure for annual leave.
get_leave_policy(policy_type) [READ ONLY]: Retrieve a local leave policy: annual or carryover.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `attendance_operations`

Use for recorded attendance, lateness, timesheets, overtime, correction, remote-work and shift-swap requests. Do not use it to request vacation or change approved records directly. Ask for missing dates, hours, correction time or target colleague.
Operations (all listed arguments required unless marked ?):
get_attendance(employee_id, month) [READ ONLY]: Read own attendance for month YYYY-MM.
check_late_arrivals(employee_id, date_range) [READ ONLY]: Find late arrivals; date_range is YYYY-MM-DD/YYYY-MM-DD. No disciplinary decisions.
report_missing_checkout(employee_id, date) [WRITE PROPOSAL, human confirmation]: Create a pending correction for a missing check-out on an existing past record.
request_overtime(employee_id, date, hours) [WRITE PROPOSAL, human confirmation]: Request overtime supported by recorded extra hours; no automatic payment.
validate_timesheet(employee_id, period) [READ ONLY]: Detect missing, duplicate, mismatched timesheet/attendance entries and approved leave conflicts. period: start/end.
request_shift_swap(employee_id, target_employee_id, shift_date) [WRITE PROPOSAL, human confirmation]: Propose a future swap between active employees with assigned shifts; human approval required.
request_remote_work(employee_id, date) [WRITE PROPOSAL, human confirmation]: Request remote work on an assigned future working day, within the monthly allowance.
request_attendance_correction(employee_id, date, corrected_time) [WRITE PROPOSAL, human confirmation]: Request a check-in correction HH:MM without overwriting the original attendance.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `employees_operations`

Use for directory teams/managers, permitted own-profile edits, transfer/document requests, onboarding/offboarding, probation and training eligibility. Use get_employee to resolve a named person; do not use directory lookup for private payroll data.
Operations (all listed arguments required unless marked ?):
update_employee_profile(employee_id, field, value) [WRITE PROPOSAL, human confirmation]: Update own phone or preferred_name only. Salary, role, identity and permissions cannot be changed.
request_department_transfer(employee_id, target_department) [WRITE PROPOSAL, human confirmation]: Request a transfer to an existing department ID or exact department name, pending HR review.
get_employee_manager(employee_id) [READ ONLY]: Get own assigned manager's directory information.
get_department_employees(department_id) [READ ONLY]: List directory-only fields for a department ID or exact department name.
create_onboarding(employee_id) [WRITE PROPOSAL, human confirmation]: Authorized HR creates or retrieves the standard employee onboarding checklist.
start_offboarding(employee_id) [WRITE PROPOSAL, human confirmation]: HR-only pending offboarding checklist. Does not disable accounts or terminate employment.
get_probation_status(employee_id) [READ ONLY]: HR or self calculates probation end date from hire date and configured duration.
request_employment_document(employee_id, document_type) [WRITE PROPOSAL, human confirmation]: Request own employment_verification or salary_certificate document for human preparation.
check_training_eligibility(employee_id, course_id) [READ ONLY]: Check own course prerequisites, capacity, existing enrollment and active status.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `payroll_operations`

Use for own/authorized fictional payslips, payroll support, expense reimbursements with receipt/category, restricted HR cases and HR policy search. Use finance_operations for purchase approval/budgets/invoices. Missing reimbursement amount or receipt requires clarification.
Operations (all listed arguments required unless marked ?):
get_payslip(employee_id, month) [READ ONLY]: Verified self or payroll role reads fictional payslip data for YYYY-MM. Amounts in EGP.
create_payroll_ticket(employee_id, issue_description) [WRITE PROPOSAL, human confirmation]: Create own confidential payroll issue ticket; content is not exposed through IT status lookup.
submit_expense_request(employee_id, amount, category, receipt_reference) [WRITE PROPOSAL, human confirmation]: Submit own positive EGP reimbursement with supported category and receipt reference; no payment.
create_hr_case(employee_id, category, description) [WRITE PROPOSAL, human confirmation]: Create own restricted HR case; return its reference without disclosing case content.
search_hr_policy(query) [READ ONLY]: Search local HR policy titles/content using case-insensitive word matching; never invent policies.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `it_operations`

Use for IT tickets/status, one-device requests, licenses and own-device warranty. Use inventory_operations/request_inventory_item for explicit bulk quantities; never silently convert a vague bulk request into one device.
Operations (all listed arguments required unless marked ?):
create_it_ticket(employee_id, issue_description) [WRITE PROPOSAL, human confirmation]: Create an IT support ticket for the selected employee; default priority normal.
get_it_ticket_status(ticket_id) [READ ONLY]: Read own IT ticket status only; cannot read payroll, HR or customer tickets.
request_software_license(employee_id, software_name) [WRITE PROPOSAL, human confirmation]: Request supported software if an unassigned license is available; allocation requires human review.
request_company_device(employee_id, device_type) [WRITE PROPOSAL, human confirmation]: Request a laptop or mouse from inventory, pending equipment approval.
check_device_warranty(asset_id) [READ ONLY]: Verify device ownership and compare its warranty expiration to company-local today.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `inventory_operations`

Use for stock, low-stock, restock, request-limit checks and quantity-based inventory requests. A quantity question is a read-only check, not a request. Ask how many if quantity is missing; use it_operations for individual assigned-device support.
Operations (all listed arguments required unless marked ?):
check_inventory(item_name) [READ ONLY]: Read available stock by exact item name, e.g. laptops or mice.
request_inventory_item(employee_id, item_id, quantity) [WRITE PROPOSAL, human confirmation]: Submit own inventory request after checking positive quantity, limits and stock. Does not reserve stock.
get_low_stock_items() [READ ONLY]: List items whose available stock is at or below their configured reorder threshold.
check_inventory_request(item_id, quantity) [READ ONLY]: Check quantity, request limit and available stock without creating a request.
get_restock_status(item_id) [READ ONLY]: Retrieve known pending purchase-order dates; never estimate an unknown arrival.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `customers_operations`

Use for the selected customer’s order status, return eligibility/request, pre-shipment address update and complaint escalation. Ask for missing order/ticket reference or new address; internal employees are not customer identities.
Operations (all listed arguments required unless marked ?):
get_order_status(order_id) [READ ONLY]: Read an order owned by the selected local customer identity.
request_product_return(order_id) [WRITE PROPOSAL, human confirmation]: Request return of own delivered order within its return window; no automatic refund.
check_return_eligibility(order_id) [READ ONLY]: Check own order against the standard 14-day return policy and configured exceptions.
update_shipping_address(order_id, new_address) [WRITE PROPOSAL, human confirmation]: Change own order address before shipment only; shipped or delivered orders are rejected.
escalate_customer_ticket(ticket_id, reason) [WRITE PROPOSAL, human confirmation]: Escalate own open customer complaint for human review.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `finance_operations`

Use for authorized invoice status/duplicates, department budget checks, purchase approval requests and overdue invoices. get_invoice_status requires ONLY invoice_id; do not ask for vendor_id or amount (those are for check_duplicate_invoice). Use payroll_operations for a personal receipt reimbursement. Do not invent invoice/vendor numbers or amounts.
Operations (all listed arguments required unless marked ?):
get_invoice_status(invoice_id) [READ ONLY]: Finance role retrieves an invoice payment status; monetary values are integer EGP cents.
check_duplicate_invoice(vendor_id, invoice_number, amount) [READ ONLY]: Finance compares vendor, invoice number and exact amount; flags number matches with amount discrepancies.
check_department_budget(department_id, amount) [READ ONLY]: Finance or the department's manager compares positive EGP amount with remaining budget.
request_expense_approval(employee_id, amount, description) [WRITE PROPOSAL, human confirmation]: Request own purchase approval against department budget; pending requests reserve budget, not payment.
get_overdue_invoices() [READ ONLY]: Finance lists unpaid invoices with due dates before company-local today.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

### `projects_operations`

Use for member-scoped task creation, status updates, overdue work, deadline conflicts and project progress. Creation requires project, assignee, title and due date. A vague task title/reference must be clarified before updating a task.
Operations (all listed arguments required unless marked ?):
create_project_task(project_id, assignee_id, title, due_date) [WRITE PROPOSAL, human confirmation]: Project member creates a task for an active member with a present/future due date.
get_overdue_tasks(project_id) [READ ONLY]: Project member retrieves incomplete tasks due before company-local today.
check_task_deadline_conflicts(employee_id, date_range) [READ ONLY]: Self or assigned manager finds incomplete deadlines close together; date_range: start/end.
update_task_status(task_id, status) [WRITE PROPOSAL, human confirmation]: Assignee or assigned project manager updates pending→in_progress/completed or in_progress→completed.
get_project_progress(project_id) [READ ONLY]: Project member receives computed total, completed, pending, in-progress and overdue counts.
First inspect describe_operation for field meanings and constraints. Ask a concise clarification for missing required information before calling a business operation. Never invent dates, IDs, quantities, amounts, receipts or approvals. Read-only metadata lookups are allowed. All calls undergo Pydantic validation and backend authorization; writes only create a proposal for a separate human HTTP confirmation, never a completed business action.

## All 60 operation contracts

Generated from service signatures, `operation_schemas.py`, and the registry. Required fields have no default. Optional fields have explicit service defaults; `get_leave_balance` has one optional `year` argument (default null/current year); other business arguments remain required. No optional reason field was invented. Read-only operations never need confirmation; every write only proposes a change for an owner-confirmed HTTP transaction. Authorization text documents services; service code remains the enforcement authority.

| Operation | Tool | Required arguments | Optional | Mode / confirmation | Authorization |
| --- | --- | --- | --- | --- | --- |
| `get_leave_balance` | `hr_operations` | `employee_id: string` | `year: union` | Read only / none | Self employee or authorized HR role. |
| `request_leave` | `hr_operations` | `employee_id: string`, `start_date: string`, `end_date: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `cancel_leave` | `hr_operations` | `request_id: integer` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `modify_leave` | `hr_operations` | `request_id: integer`, `new_start_date: string`, `new_end_date: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `check_leave_overlap` | `hr_operations` | `employee_id: string`, `start_date: string`, `end_date: string` | none | Read only / none | Self employee or authorized HR role. |
| `check_team_leave_conflict` | `hr_operations` | `employee_ids: array`, `start_date: string`, `end_date: string` | none | Read only / none | HR role or assigned manager of every requested employee. |
| `calculate_leave_days` | `hr_operations` | `start_date: string`, `end_date: string`, `employee_id: string` | none | Read only / none | Self employee or authorized HR role. |
| `review_leave_request` | `hr_operations` | `request_id: integer`, `decision: string` | none | Write proposal / human confirmation | Assigned manager only; cannot review own leave; rechecked at confirmation. |
| `get_leave_history` | `hr_operations` | `employee_id: string`, `year: integer` | none | Read only / none | Self employee or authorized HR role. |
| `calculate_leave_carryover` | `hr_operations` | `employee_id: string`, `year: integer` | none | Read only / none | Self employee or authorized HR role. |
| `check_leave_eligibility` | `hr_operations` | `employee_id: string` | none | Read only / none | Self employee or authorized HR role. |
| `get_leave_policy` | `hr_operations` | `policy_type: string` | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `get_attendance` | `attendance_operations` | `employee_id: string`, `month: string` | none | Read only / none | Self employee or authorized HR role. |
| `check_late_arrivals` | `attendance_operations` | `employee_id: string`, `date_range: string` | none | Read only / none | Self employee or authorized HR role. |
| `report_missing_checkout` | `attendance_operations` | `employee_id: string`, `date: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `request_overtime` | `attendance_operations` | `employee_id: string`, `date: string`, `hours: number` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `validate_timesheet` | `attendance_operations` | `employee_id: string`, `period: string` | none | Read only / none | Self employee or authorized HR role. |
| `request_shift_swap` | `attendance_operations` | `employee_id: string`, `target_employee_id: string`, `shift_date: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `request_remote_work` | `attendance_operations` | `employee_id: string`, `date: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `request_attendance_correction` | `attendance_operations` | `employee_id: string`, `date: string`, `corrected_time: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `get_employee` | `get_employee` | `name: string` | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `update_employee_profile` | `employees_operations` | `employee_id: string`, `field: string`, `value: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `request_department_transfer` | `employees_operations` | `employee_id: string`, `target_department: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `get_employee_manager` | `employees_operations` | `employee_id: string` | none | Read only / none | Self employee or authorized HR role. |
| `get_department_employees` | `employees_operations` | `department_id: string` | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `create_onboarding` | `employees_operations` | `employee_id: string` | none | Write proposal / human confirmation | Authorized HR role only; creates a pending human-reviewed workflow. |
| `start_offboarding` | `employees_operations` | `employee_id: string` | none | Write proposal / human confirmation | Authorized HR role only; creates a pending human-reviewed workflow. |
| `get_probation_status` | `employees_operations` | `employee_id: string` | none | Read only / none | Self employee or authorized HR role. |
| `request_employment_document` | `employees_operations` | `employee_id: string`, `document_type: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `check_training_eligibility` | `employees_operations` | `employee_id: string`, `course_id: string` | none | Read only / none | Self employee or authorized HR role. |
| `get_payslip` | `payroll_operations` | `employee_id: string`, `month: string` | none | Read only / none | Self employee or authorized payroll role; fictional payslip only. |
| `create_payroll_ticket` | `payroll_operations` | `employee_id: string`, `issue_description: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `submit_expense_request` | `payroll_operations` | `employee_id: string`, `amount: number`, `category: string`, `receipt_reference: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `create_hr_case` | `payroll_operations` | `employee_id: string`, `category: string`, `description: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `search_hr_policy` | `payroll_operations` | `query: string` | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `create_it_ticket` | `it_operations` | `employee_id: string`, `issue_description: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `get_it_ticket_status` | `it_operations` | `ticket_id: integer` | none | Read only / none | Owner of the IT ticket only; payroll/HR/customer tickets excluded. |
| `request_software_license` | `it_operations` | `employee_id: string`, `software_name: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `request_company_device` | `it_operations` | `employee_id: string`, `device_type: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `check_device_warranty` | `it_operations` | `asset_id: string` | none | Read only / none | Assigned owner of the device only. |
| `check_inventory` | `inventory_operations` | `item_name: string` | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `request_inventory_item` | `inventory_operations` | `employee_id: string`, `item_id: string`, `quantity: integer` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `get_low_stock_items` | `inventory_operations` | none | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `check_inventory_request` | `inventory_operations` | `item_id: string`, `quantity: integer` | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `get_restock_status` | `inventory_operations` | `item_id: string` | none | Read only / none | Internal employee directory/policy access only; no customer access or private payroll fields. |
| `get_order_status` | `customers_operations` | `order_id: string` | none | Read only / none | Selected customer must own the order. |
| `request_product_return` | `customers_operations` | `order_id: string` | none | Write proposal / human confirmation | Selected customer must own the order. |
| `check_return_eligibility` | `customers_operations` | `order_id: string` | none | Read only / none | Selected customer must own the order. |
| `update_shipping_address` | `customers_operations` | `order_id: string`, `new_address: string` | none | Write proposal / human confirmation | Selected customer must own the order. |
| `escalate_customer_ticket` | `customers_operations` | `ticket_id: integer`, `reason: string` | none | Write proposal / human confirmation | Selected customer must own the open customer complaint ticket. |
| `get_invoice_status` | `finance_operations` | `invoice_id: string` | none | Read only / none | Authorized finance role only. |
| `check_duplicate_invoice` | `finance_operations` | `vendor_id: string`, `invoice_number: string`, `amount: number` | none | Read only / none | Authorized finance role only. |
| `check_department_budget` | `finance_operations` | `department_id: string`, `amount: number` | none | Read only / none | Finance role or manager of the requested department. |
| `request_expense_approval` | `finance_operations` | `employee_id: string`, `amount: number`, `description: string` | none | Write proposal / human confirmation | Self employee only; identity is supplied by the local application, never proven by the argument. |
| `get_overdue_invoices` | `finance_operations` | none | none | Read only / none | Authorized finance role only. |
| `create_project_task` | `projects_operations` | `project_id: string`, `assignee_id: string`, `title: string`, `due_date: string` | none | Write proposal / human confirmation | Project membership required; assignee must be an active project member. |
| `get_overdue_tasks` | `projects_operations` | `project_id: string` | none | Read only / none | Project membership required. |
| `check_task_deadline_conflicts` | `projects_operations` | `employee_id: string`, `date_range: string` | none | Read only / none | Self or assigned manager; results restricted to projects the caller belongs to. |
| `update_task_status` | `projects_operations` | `task_id: integer`, `status: string` | none | Write proposal / human confirmation | Task assignee or their assigned manager, plus project membership. |
| `get_project_progress` | `projects_operations` | `project_id: string` | none | Read only / none | Project membership required. |

## Shared field meanings and constraints

These field definitions are generated from the actual schemas, not a separate handwritten contract. ISO date strings are retained for API compatibility but their real calendar dates, year range and date ordering are validated by Pydantic. Business eligibility, balances, ownership, supported policy categories and transitions remain service checks.

| Field | Description | JSON-schema constraints |
| --- | --- | --- |
| `employee_id` | Target stable employee ID, e.g. E001. For self-service use the trusted application employee_id; for another employee resolve their exact name with get_employee. Never invent an ID; authorization is checked independently. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `year` | Optional calendar year (1900–2200). Omitted/null uses current year. Explicit years must come from the user or unambiguous active Studio conversation context. | `{"anyOf": [{"maximum": 2200, "minimum": 1900, "type": "integer"}, {"type": "null"}], "default": null}` |
| `start_date` | First inclusive date, YYYY-MM-DD with an explicit year. Ask if the date or year is missing/ambiguous. | `{"format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `end_date` | Last inclusive date, YYYY-MM-DD with an explicit year, on/after start_date. Do not infer an end date from vague duration. | `{"format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `request_id` | Positive existing leave request ID. Require the user to identify the request; never choose an arbitrary request from history. | `{"exclusiveMinimum": 0, "type": "integer"}` |
| `new_start_date` | Replacement first inclusive leave date, YYYY-MM-DD with explicit year. | `{"format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `new_end_date` | Replacement last inclusive leave date, YYYY-MM-DD with explicit year, on/after new_start_date. | `{"format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `employee_ids` | Distinct stable employee IDs for the proposed simultaneous leave. Resolve named colleagues; HR/assigned-manager authorization is required. | `{"items": {"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}, "maxItems": 100, "minItems": 1, "type": "array"}` |
| `decision` | Explicit manager decision: approve or reject. Assigned-manager permission and separate human confirmation are required. | `{"enum": ["approve", "reject"], "type": "string"}` |
| `policy_type` | Exact leave policy type: annual or carryover. Use search_hr_policy for other company policies. | `{"enum": ["annual", "carryover"], "type": "string"}` |
| `month` | Calendar month YYYY-MM, including year. Ask for an omitted year; do not assume the current year. | `{"pattern": "^\\d{4}-\\d{2}$", "type": "string"}` |
| `date_range` | Inclusive date range formatted YYYY-MM-DD/YYYY-MM-DD; both endpoints and years are required. | `{"pattern": "^\\d{4}-\\d{2}-\\d{2}/\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `date` | Specific attendance/remote-work calendar date, YYYY-MM-DD with explicit year. A precise relative date may be resolved from the trusted company-local date. | `{"format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `hours` | Explicit positive overtime hours for the given date. Recorded-hours and policy limits are checked by the service. | `{"exclusiveMinimum": 0, "maximum": 24, "type": "number"}` |
| `period` | Inclusive timesheet period formatted YYYY-MM-DD/YYYY-MM-DD; both endpoints and years are required. | `{"pattern": "^\\d{4}-\\d{2}-\\d{2}/\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `target_employee_id` | Stable ID of the explicitly named colleague receiving the shift swap; resolve with get_employee, never guess. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `shift_date` | Exact assigned shift date, YYYY-MM-DD with explicit year; ask if ambiguous. | `{"format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `corrected_time` | Requested replacement check-in time in company-local HH:MM, 24-hour format. Does not directly overwrite attendance. | `{"pattern": "^\\d{2}:\\d{2}$", "type": "string"}` |
| `name` | Explicit employee name, matched exactly ignoring surrounding whitespace and case. Partial/ambiguous names must be clarified; directory data only. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `field` | Approved own-profile field only: phone or preferred_name. Roles, salary and permissions cannot be changed. | `{"enum": ["phone", "preferred_name"], "type": "string"}` |
| `value` | Explicit replacement profile value supplied by the user; never fabricate contact information. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `target_department` | Explicit requested destination department ID or exact name; never choose a destination for the employee. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `department_id` | Known department ID or exact name, e.g. ENG or Engineering; the backend resolves the canonical ID. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `document_type` | Explicit document type, e.g. employment_verification or salary_certificate; supported types are checked against current policy. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `course_id` | Exact training course ID supplied by the user; unknown IDs are rejected by the service. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `issue_description` | User-provided description of the IT/payroll problem, 1–2000 characters; do not invent symptoms or financial facts. | `{"maxLength": 2000, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `amount` | Explicit positive EGP amount with at most two decimal places. Do not infer an amount, currency conversion or budget approval. | `{"exclusiveMinimum": 0, "maximum": 100000000, "type": "number"}` |
| `category` | User-provided case/expense category. Reimbursement categories are checked against current configured policy. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `receipt_reference` | Actual demo receipt reference supplied by the user; required for reimbursement. Never invent a receipt. | `{"maxLength": 200, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `description` | User-provided HR case or purchase description, 1–2000 characters. Ask when the purpose/content is missing. | `{"maxLength": 2000, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `query` | Specific HR policy topic to search, such as remote work. This does not search private records. | `{"maxLength": 200, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `ticket_id` | Positive existing ticket reference supplied by the user or unambiguously returned by an authorized lookup. Never invent it. | `{"exclusiveMinimum": 0, "type": "integer"}` |
| `software_name` | Explicit software product name, e.g. Microsoft Office; availability and existing assignments are checked by the service. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `device_type` | Requested device type: laptop/laptops or mouse/mice. Use request_inventory_item when an explicit bulk quantity is requested. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `asset_id` | Known assigned device asset ID, e.g. ASSET-1. Ask for the asset reference if missing; ownership is enforced. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `item_name` | Exact inventory item name, e.g. laptops or mice. This is a stock lookup, not a device request. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `item_id` | Inventory item ID returned by check_inventory, e.g. LAPTOP. Resolve an item name through stock lookup rather than inventing an ID. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `quantity` | Explicit positive integer quantity. Words such as some or a few do not specify a quantity; ask the user. | `{"exclusiveMinimum": 0, "type": "integer"}` |
| `order_id` | Exact customer order reference, e.g. ORD-1. Ask for the order ID; never select an arbitrary order. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `new_address` | Complete new fictional shipping address supplied by the customer; never invent an address. | `{"maxLength": 500, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `reason` | User-provided reason for customer complaint escalation, 1–2000 characters. | `{"maxLength": 2000, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `invoice_id` | Exact invoice reference, e.g. INV-100; finance authorization is required. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `vendor_id` | Known vendor reference for duplicate-invoice detection; do not invent a vendor. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `invoice_number` | Vendor invoice number exactly as supplied; distinct from the internal invoice ID. | `{"maxLength": 100, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `project_id` | Known project ID or exact project name, e.g. ALPHA or Project Alpha. Ask which project if omitted. | `{"maxLength": 200, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `assignee_id` | Stable ID of the explicitly named task assignee; resolve with get_employee. Do not substitute the current employee unless requested. | `{"maxLength": 100, "minLength": 1, "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]*$", "type": "string"}` |
| `title` | Explicit task title supplied by the user. Naming the assignee alone is insufficient. | `{"maxLength": 200, "minLength": 1, "pattern": "\\S", "type": "string"}` |
| `due_date` | Task deadline, YYYY-MM-DD with explicit year; required even when project/title/assignee are known. | `{"format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "type": "string"}` |
| `task_id` | Positive existing task ID. If a title matches multiple tasks, ask which ID; do not update an arbitrary task. | `{"exclusiveMinimum": 0, "type": "integer"}` |
| `status` | Requested exact task status. Allowed transitions and assignee/manager permission are enforced by the service. | `{"enum": ["pending", "in_progress", "completed"], "type": "string"}` |

Additional Pydantic validators enforce valid calendar/clock values, date-range ordering/length, distinct employee lists, phone syntax and exact two-decimal money precision. Those callable validators are not fully expressible as JSON-schema constraints. Numeric values are finite and positive; IDs/counts are strict types; unexpected fields are forbidden.

## Missing information, identity and rejection behavior

* Tools inspect `describe_operation` for required/optional fields, provenance descriptions and authorization. Unsupported names return a catalog or a structured envelope error.
* Missing input returns `code`, `operation`, `missing_fields`, safe field errors, `clarification_required` and `next_step`. Values, stack traces and Pydantic URLs are not echoed.
* Known self identity is supplied by the application. Metadata/error hints expose the selected employee ID to the model, preventing an unnecessary user-ID question; they do not silently replace another target or prove authorization.
* Partial/case-insensitively ambiguous employee names are not arbitrarily resolved. Request/task/order/ticket references must be identified; a multi-request cancellation must ask which ID.
* FastAPI and default Studio requests remain independent. Opt-in Studio human-message memory supports bounded same-thread clarification; see MEMORY_FIX_RESULTS.md. Non-required fields must not be requested as prerequisites.
* Month/day without a year always requires clarification. A request-local tool guard blocks invented years before service dispatch. Explicit four-digit years (including Arabic digits) and supported precise relative dates are checked against the original user message. Supported relative forms are today/tomorrow/yesterday, current month/week ranges and current year. Week means Monday–Sunday.
* Direct HTTP operation calls supply explicit canonical arguments and do not pass through the natural-language year guard. They still undergo the identical Pydantic/service/authorization/confirmation checks.
* All consequential changes retain immutable proposals, expiry, ownership, atomic revalidation and exactly-once confirmation receipts. The model cannot invoke confirmation.

## Verification and live results

Verified during this audit: **85 offline tests passed** (69 original business tests plus 16 focused contract tests). Offline tests preserve the original 69 business tests and add focused metadata/schema, routing, safe error, ambiguity, context and provenance tests. Scripted-model tests force tool attempts to verify the guard; they do **not** prove real model understanding.

Real live testing: **45 OpenAI model calls across 27 independent requests**, including failures and targeted retests. All calls used fictional temporary databases; no human confirmations were executed.

| Run | Cases | Passed | Failed | Model calls |
| --- | --- | --- | --- | --- |
| initial | 12 | 11 | 1 | 18 |
| year-and-complete-retest | 3 | 2 | 1 | 4 |
| module-selection-and-year-retest | 10 | 9 | 1 | 18 |
| invoice-and-permission-targeted-retest | 2 | 2 | 0 | 5 |

Detailed original inputs, tool/operation/arguments, clarification flags, unsafe attempts, backend results, final responses and explicit pass/fail expectations are retained in [LIVE_TOOL_CHECKS.json](LIVE_TOOL_CHECKS.json). Earlier failures are not erased by later passes.

Observed failures: an initially yearless leave request caused a premature proposal (no business data changed); a complete request later asked for an already trusted employee ID; invoice status once requested an unrelated vendor ID. Repairs added the calendar guard, trusted-ID error hints and clearer neighboring-operation guidance. The unauthorized-payslip initial response also overstated policy about payroll administrators; the backend denial wording/prompt now identify the selected application account rather than trusting a role claim.

## Reproduce

```bash
python -m unittest discover -s tests -v
python scripts/generate_tool_audit.py
# Lists cases only: zero paid calls
python scripts/live_tool_checks.py
# Explicitly opt in to a small subset
python scripts/live_tool_checks.py --live --cases complete_leave,missing_leave_dates,invalid_quantity --max-model-calls 10 --output live-local-results.json
```

## Remaining limitations

Real LLM behavior is variable: passing a smoke check is not proof of consistent extraction, clarification or all-60 live coverage. Recorded pass/fail uses explicit tool/argument/keyword expectations, not an LLM judge; review complete traces for semantic mistakes or invented policy language. The generic dispatcher remains, supported by exact discovery and backend enforcement. The year guard is deliberately narrow, not a general natural-language provenance parser: it does not prove every quantity, identifier or amount was grounded, and does not resolve arbitrary relative phrases. Valid-looking invented arguments can still be proposed; human review/confirmation remains mandatory. The later opt-in Studio memory update uses existing checkpoint state; no new memory database, business tables, agents or evaluator model were added.

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
