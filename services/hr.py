"""Leave balances, calendars, coverage and manager review."""

from datetime import date, timedelta
from database import db, one, rows, policy, today, utcnow
from services.common import (
    operation,
    require,
    self_access,
    employee,
    actor,
    role,
    manager_access,
    dates,
    day,
    text,
)


def eligible(eid):
    p = employee(eid)
    tenure = (today() - day(p["hire_date"])).days
    return {
        "eligible": p["status"] == "active" and tenure >= policy("eligibility_days"),
        "tenure_days": tenure,
        "minimum_days": policy("eligibility_days"),
        "reason": "Active employment and minimum tenure are required.",
    }


def working_days(eid, start, end):
    a, b = dates(start, end)
    p = employee(eid)
    require(a >= day(p["hire_date"]), "Leave cannot precede the hire date.")
    holidays = {
        r["day"]
        for r in rows(
            "SELECT day FROM holidays WHERE day BETWEEN ? AND ?", (start, end)
        )
    }
    weekends = policy("weekends")
    return sum(
        (a + timedelta(days=i)).weekday() not in weekends
        and str(a + timedelta(days=i)) not in holidays
        for i in range((b - a).days + 1)
    )


def balance(eid, year):
    require(1900 <= year <= 2200, "Year must be between 1900 and 2200.")
    employee(eid)
    found = one(
        "SELECT annual_allowance FROM leave_balances WHERE employee_id=? AND year=?",
        (eid, year),
    )
    allowance = found["annual_allowance"] if found else policy("annual_allowance")
    used = one(
        "SELECT COALESCE(SUM(deducted_days),0) AS used FROM leave_requests WHERE employee_id=? AND substr(start_date,1,4)=? AND status='approved'",
        (eid, str(year)),
    )["used"]
    return {
        "employee_id": eid,
        "year": year,
        "annual_allowance": allowance,
        "used_days": used,
        "remaining_days": allowance - used,
    }


def overlaps(eid, start, end, exclude=0):
    dates(start, end)
    return rows(
        "SELECT id,start_date,end_date,status FROM leave_requests WHERE employee_id=? AND status IN ('pending','approved') AND start_date<=? AND end_date>=? AND id<>?",
        (eid, end, start, exclude),
    )


def coverage(ids, start, end, exclude=0):
    a, b = dates(start, end)
    require(
        bool(ids) and len(ids) == len(set(ids)) and len(ids) <= 100,
        "Provide 1–100 distinct employee IDs.",
    )
    departments = {employee(e)["department_id"] for e in ids}
    conflicts = []
    for dept in departments:
        members = {
            r["id"]
            for r in rows(
                "SELECT id FROM employees WHERE department_id=? AND status='active'",
                (dept,),
            )
        }
        minimum = one("SELECT min_staff FROM departments WHERE id=?", (dept,))[
            "min_staff"
        ]
        for offset in range((b - a).days + 1):
            d = a + timedelta(days=offset)
            if d.weekday() in policy("weekends") or one(
                "SELECT day FROM holidays WHERE day=?", (str(d),)
            ):
                continue
            away = {
                r["employee_id"]
                for r in rows(
                    "SELECT employee_id FROM leave_requests WHERE status='approved' AND start_date<=? AND end_date>=? AND id<>?",
                    (str(d), str(d), exclude),
                )
            }
            away.update(ids)
            available = len(members - away)
            if available < minimum:
                conflicts.append(
                    {
                        "department_id": dept,
                        "date": str(d),
                        "available": available,
                        "minimum": minimum,
                    }
                )
    return {
        "conflicts": conflicts,
        "manager_review_required": bool(conflicts),
        "coverage_sufficient": not conflicts,
    }


def request_row(rid):
    require(rid > 0, "Request ID must be positive.")
    r = one("SELECT * FROM leave_requests WHERE id=?", (rid,))
    require(r is not None, "Leave request not found.", "not_found")
    return r


def validate_leave(eid, start, end, exclude=0, credit=0):
    a, b = dates(start, end, True)
    require(a.year == b.year, "Submit separate requests for different calendar years.")
    require(eligible(eid)["eligible"], "Employee is not eligible for annual leave.")
    count = working_days(eid, start, end)
    require(count > 0, "Date range contains no eligible working days.")
    require(
        not overlaps(eid, start, end, exclude),
        "Dates overlap pending or approved leave.",
        "conflict",
    )
    require(
        count <= balance(eid, a.year)["remaining_days"] + credit,
        "Insufficient leave balance.",
    )
    return count


@operation("hr")
def get_leave_balance(employee_id: str, year: int | None = None) -> dict:
    """Get allowance, approved usage and remaining days for optional year; omitted/null uses current year."""
    self_access(employee_id, "hr")
    return balance(employee_id, today().year if year is None else year)


@operation("hr", write=True)
def request_leave(employee_id: str, start_date: str, end_date: str) -> dict:
    """Request future annual leave; inclusive dates YYYY-MM-DD. Pending requests do not deduct days."""
    self_access(employee_id)
    count = validate_leave(employee_id, start_date, end_date)
    cur = db().execute(
        "INSERT INTO leave_requests(employee_id,start_date,end_date,days,status,created_at) VALUES (?,?,?,?,?,?)",
        (employee_id, start_date, end_date, count, "pending", utcnow()),
    )
    return {
        "request_id": cur.lastrowid,
        "status": "pending",
        "requested_days": count,
        "coverage": coverage([employee_id], start_date, end_date),
        "balance": balance(employee_id, day(start_date).year),
    }


@operation("hr", write=True)
def cancel_leave(request_id: int) -> dict:
    """Cancel own future pending or approved leave; approved deductions are restored once."""
    r = request_row(request_id)
    self_access(r["employee_id"])
    require(
        r["status"] in ["pending", "approved"],
        "Only pending or approved leave may be cancelled.",
    )
    require(
        day(r["start_date"]) >= today(), "Started or past leave cannot be cancelled."
    )
    db().execute(
        "UPDATE leave_requests SET status='cancelled',deducted_days=0 WHERE id=?",
        (request_id,),
    )
    return {
        "request_id": request_id,
        "status": "cancelled",
        "restored_days": r["deducted_days"],
        "balance": balance(r["employee_id"], day(r["start_date"]).year),
    }


@operation("hr", write=True)
def modify_leave(request_id: int, new_start_date: str, new_end_date: str) -> dict:
    """Modify own future leave. Previously approved leave returns to pending for reapproval."""
    r = request_row(request_id)
    self_access(r["employee_id"])
    require(
        r["status"] in ["pending", "approved"] and day(r["start_date"]) >= today(),
        "Only future pending or approved leave can be modified.",
    )
    credit = (
        r["deducted_days"]
        if day(new_start_date).year == day(r["start_date"]).year
        else 0
    )
    count = validate_leave(
        r["employee_id"], new_start_date, new_end_date, request_id, credit
    )
    require(
        (new_start_date, new_end_date) != (r["start_date"], r["end_date"]),
        "Dates are unchanged.",
        "conflict",
    )
    db().execute(
        "UPDATE leave_requests SET start_date=?,end_date=?,days=?,status='pending',deducted_days=0,reviewed_by=NULL,reviewed_at=NULL WHERE id=?",
        (new_start_date, new_end_date, count, request_id),
    )
    return {
        "request_id": request_id,
        "old_dates": [r["start_date"], r["end_date"]],
        "new_dates": [new_start_date, new_end_date],
        "requested_days": count,
        "status": "pending",
        "reapproval_required": True,
    }


@operation("hr")
def check_leave_overlap(employee_id: str, start_date: str, end_date: str) -> dict:
    """Check own leave dates against pending and approved bookings."""
    self_access(employee_id, "hr")
    found = overlaps(employee_id, start_date, end_date)
    return {"overlap": bool(found), "requests": found}


@operation("hr")
def check_team_leave_conflict(
    employee_ids: list[str], start_date: str, end_date: str
) -> dict:
    """HR or assigned managers check simultaneous leave against department minimum staffing."""
    user = role("manager", "hr")
    for eid in employee_ids:
        if "hr" not in user["roles"]:
            manager_access(eid)
    return coverage(employee_ids, start_date, end_date)


@operation("hr")
def calculate_leave_days(start_date: str, end_date: str, employee_id: str) -> dict:
    """Count working days inclusive of endpoints, excluding weekends and company holidays."""
    self_access(employee_id, "hr")
    return {
        "working_days": working_days(employee_id, start_date, end_date),
        "weekends": policy("weekends"),
        "holidays": rows(
            "SELECT * FROM holidays WHERE day BETWEEN ? AND ?", (start_date, end_date)
        ),
    }


@operation("hr", write=True)
def review_leave_request(request_id: int, decision: str) -> dict:
    """Assigned manager approves or rejects a pending leave request. decision: approve or reject."""
    r = request_row(request_id)
    manager_access(r["employee_id"])
    require(decision in ["approve", "reject"], "Decision must be approve or reject.")
    require(
        r["status"] == "pending", "Only pending requests can be reviewed.", "conflict"
    )
    if decision == "approve":
        count = validate_leave(
            r["employee_id"], r["start_date"], r["end_date"], request_id
        )
        require(
            count == r["days"], "Calendar changed; modify the request before approval."
        )
        require(
            coverage([r["employee_id"]], r["start_date"], r["end_date"], request_id)[
                "coverage_sufficient"
            ],
            "Insufficient staffing; manager must resolve coverage before approval.",
        )
    status = "approved" if decision == "approve" else "rejected"
    db().execute(
        "UPDATE leave_requests SET status=?,deducted_days=?,reviewed_by=?,reviewed_at=? WHERE id=?",
        (
            status,
            r["days"] if decision == "approve" else 0,
            actor()["employee_id"],
            utcnow(),
            request_id,
        ),
    )
    return {
        "request_id": request_id,
        "status": status,
        "balance": balance(r["employee_id"], day(r["start_date"]).year),
    }


@operation("hr")
def get_leave_history(employee_id: str, year: int) -> dict:
    """Get own leave requests and statuses for a calendar year."""
    self_access(employee_id, "hr")
    require(1900 <= year <= 2200, "Invalid year.")
    return {
        "requests": rows(
            "SELECT * FROM leave_requests WHERE employee_id=? AND substr(start_date,1,4)=? ORDER BY start_date",
            (employee_id, str(year)),
        )
    }


@operation("hr")
def calculate_leave_carryover(employee_id: str, year: int) -> dict:
    """Calculate carryover eligibility, limit and next-year expiry. Does not credit a balance."""
    self_access(employee_id, "hr")
    b = balance(employee_id, year)
    expiry = date(
        year + 1, policy("carryover_expiry_month"), policy("carryover_expiry_day")
    )
    eligible_days = min(b["remaining_days"], policy("carryover_limit"))
    return {
        **b,
        "carryover_limit": policy("carryover_limit"),
        "eligible_days": eligible_days,
        "available_as_of_today": (
            eligible_days if date(year + 1, 1, 1) <= today() <= expiry else 0
        ),
        "expires_on": str(expiry),
        "credited": False,
        "note": "Projection only before year end; transfer is a human HR process.",
    }


@operation("hr")
def check_leave_eligibility(employee_id: str) -> dict:
    """Check active employment and configured minimum tenure for annual leave."""
    self_access(employee_id, "hr")
    return eligible(employee_id)


@operation("hr")
def get_leave_policy(policy_type: str) -> dict:
    """Retrieve a local leave policy: annual or carryover."""
    role("employee", "hr", "manager")
    require(
        policy_type in ["annual", "carryover"],
        "Supported leave policies: annual, carryover.",
    )
    return one("SELECT * FROM policies WHERE id=?", (policy_type,))
