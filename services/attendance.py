"""Attendance checks and pending corrections; no direct record overwrites."""

from datetime import datetime, timedelta
from database import one, rows, policy, today
from services.common import (
    operation,
    require,
    self_access,
    day,
    dates,
    clock,
    period,
    month_range,
    pending,
)


def record(eid, d):
    day(d)
    require(day(d) <= today(), "Attendance date cannot be in the future.")
    found = one("SELECT * FROM attendance WHERE employee_id=? AND day=?", (eid, d))
    require(found is not None, "No attendance record for that day.", "not_found")
    return found


def schedule(eid, d):
    return one("SELECT * FROM shifts WHERE employee_id=? AND day=?", (eid, d)) or {
        "start_time": policy("schedule_start"),
        "end_time": policy("schedule_end"),
    }


@operation("attendance")
def get_attendance(employee_id: str, month: str) -> dict:
    """Read own attendance for month YYYY-MM."""
    self_access(employee_id, "hr")
    a, b = month_range(month)
    found = rows(
        "SELECT day,check_in,check_out FROM attendance WHERE employee_id=? AND day BETWEEN ? AND ? ORDER BY day",
        (employee_id, str(a), str(b)),
    )
    return {
        "records": found,
        "recorded_days": len(found),
        "message": "Attendance retrieved." if found else "No records.",
    }


@operation("attendance")
def check_late_arrivals(employee_id: str, date_range: str) -> dict:
    """Find late arrivals; date_range is YYYY-MM-DD/YYYY-MM-DD. No disciplinary decisions."""
    self_access(employee_id, "hr")
    a, b = period(date_range)
    late = []
    for r in rows(
        "SELECT * FROM attendance WHERE employee_id=? AND day BETWEEN ? AND ?",
        (employee_id, str(a), str(b)),
    ):
        if r["check_in"]:
            start = schedule(employee_id, r["day"])["start_time"]
            minutes = (
                datetime.combine(day(r["day"]), clock(r["check_in"]))
                - datetime.combine(day(r["day"]), clock(start))
            ).total_seconds() / 60
            if minutes > policy("grace_minutes"):
                late.append(
                    {
                        "date": r["day"],
                        "delay_minutes": int(minutes),
                        "beyond_grace_minutes": int(minutes) - policy("grace_minutes"),
                    }
                )
    return {"late_arrivals": late, "grace_minutes": policy("grace_minutes")}


@operation("attendance", write=True)
def report_missing_checkout(employee_id: str, date: str) -> dict:
    """Create a pending correction for a missing check-out on an existing past record."""
    self_access(employee_id)
    r = record(employee_id, date)
    require(
        r["check_in"] and not r["check_out"],
        "Record must have a check-in and no check-out.",
    )
    require(day(date) < today(), "Report missing check-out after that day ends.")
    return pending("missing_checkout", employee_id, {"date": date})


@operation("attendance", write=True)
def request_overtime(employee_id: str, date: str, hours: float) -> dict:
    """Request overtime supported by recorded extra hours; no automatic payment."""
    self_access(employee_id)
    r = record(employee_id, date)
    require(
        0 < hours <= policy("max_overtime_hours"),
        "Hours exceed the positive daily overtime limit.",
    )
    require(r["check_in"] and r["check_out"], "Complete attendance required.")
    start = datetime.combine(day(date), clock(r["check_in"]))
    end = datetime.combine(day(date), clock(r["check_out"]))
    extra = max(0, (end - start).total_seconds() / 3600 - policy("daily_hours"))
    require(hours <= extra, "Requested overtime exceeds recorded extra hours.")
    existing = rows(
        "SELECT payload FROM requests WHERE kind='overtime' AND owner_id=? AND status IN ('pending','approved')",
        (employee_id,),
    )
    import json

    require(
        not any(json.loads(r["payload"])["date"] == date for r in existing),
        "Overtime already requested for that date.",
        "conflict",
    )
    return pending("overtime", employee_id, {"date": date, "hours": hours})


@operation("attendance")
def validate_timesheet(employee_id: str, period: str) -> dict:
    """Detect missing, duplicate, mismatched timesheet/attendance entries and approved leave conflicts. period: start/end."""
    self_access(employee_id, "hr")
    a, b = dates(*period.split("/", 1)) if "/" in period else (None, None)
    require(a is not None, "Use period YYYY-MM-DD/YYYY-MM-DD.")
    require(
        b <= today(), "Timesheet validation supports completed calendar dates only."
    )
    issues = []
    for offset in range((b - a).days + 1):
        d = str(a + timedelta(days=offset))
        if day(d).weekday() in policy("weekends") or one(
            "SELECT day FROM holidays WHERE day=?", (d,)
        ):
            continue
        ts = rows(
            "SELECT * FROM timesheets WHERE employee_id=? AND day=?", (employee_id, d)
        )
        att = one(
            "SELECT * FROM attendance WHERE employee_id=? AND day=?", (employee_id, d)
        )
        leave = one(
            "SELECT id FROM leave_requests WHERE employee_id=? AND status='approved' AND start_date<=? AND end_date>=?",
            (employee_id, d, d),
        )
        reasons = []
        if not leave and not ts:
            reasons.append("missing_timesheet")
        if len(ts) > 1:
            reasons.append("duplicate_timesheet")
        if not leave and (not att or not att["check_in"] or not att["check_out"]):
            reasons.append("missing_attendance_entry")
        if leave and (ts or att):
            reasons.append("approved_leave_conflict")
        if att and att["check_in"] and att["check_out"] and ts:
            recorded = (
                datetime.combine(day(d), clock(att["check_out"]))
                - datetime.combine(day(d), clock(att["check_in"]))
            ).total_seconds() / 3600
            if abs(sum(t["hours"] for t in ts) - recorded) > 0.02:
                reasons.append("hours_mismatch")
        if reasons:
            issues.append({"date": d, "issues": reasons})
    return {"inconsistencies": issues}


@operation("attendance", write=True)
def request_shift_swap(
    employee_id: str, target_employee_id: str, shift_date: str
) -> dict:
    """Propose a future swap between active employees with assigned shifts; human approval required."""
    self_access(employee_id)
    require(employee_id != target_employee_id, "Choose a different employee.")
    from services.common import employee

    require(
        employee(employee_id)["status"] == "active"
        and employee(target_employee_id)["status"] == "active",
        "Both employees must be active.",
    )
    dates(shift_date, shift_date, True)
    for eid in [employee_id, target_employee_id]:
        require(
            one("SELECT 1 FROM shifts WHERE employee_id=? AND day=?", (eid, shift_date))
            is not None,
            "Both employees need assigned shifts.",
        )
        require(
            not one(
                "SELECT 1 FROM leave_requests WHERE employee_id=? AND status IN ('pending','approved') AND start_date<=? AND end_date>=?",
                (eid, shift_date, shift_date),
            ),
            "Shift conflicts with leave.",
        )
    import json

    for r in rows(
        "SELECT owner_id,payload FROM requests WHERE kind='shift_swap' AND status='pending'"
    ):
        data = json.loads(r["payload"])
        require(
            data["date"] != shift_date
            or not (
                {r["owner_id"], data["target"]} & {employee_id, target_employee_id}
            ),
            "A pending swap already involves this shift.",
            "conflict",
        )
    return pending(
        "shift_swap", employee_id, {"target": target_employee_id, "date": shift_date}
    )


@operation("attendance", write=True)
def request_remote_work(employee_id: str, date: str) -> dict:
    """Request remote work on an assigned future working day, within the monthly allowance."""
    p = self_access(employee_id)
    dates(date, date, True)
    require(
        p["status"] == "active" and p["remote_allowed"],
        "Employee is not eligible for remote work.",
    )
    require(
        day(date).weekday() not in policy("weekends")
        and not one("SELECT day FROM holidays WHERE day=?", (date,)),
        "Date is not a working day.",
    )
    require(
        one("SELECT 1 FROM shifts WHERE employee_id=? AND day=?", (employee_id, date))
        is not None,
        "No assigned work schedule on this date.",
    )
    require(
        not one(
            "SELECT 1 FROM leave_requests WHERE employee_id=? AND status IN ('pending','approved') AND start_date<=? AND end_date>=?",
            (employee_id, date, date),
        ),
        "Date conflicts with leave.",
    )
    import json

    used = [
        json.loads(r["payload"])["date"]
        for r in rows(
            "SELECT payload FROM requests WHERE kind='remote_work' AND owner_id=? AND status IN ('pending','approved')",
            (employee_id,),
        )
    ]
    require(
        date not in used, "Remote work already requested for this date.", "conflict"
    )
    require(
        sum(d[:7] == date[:7] for d in used) < policy("remote_days_month"),
        "Monthly remote-work allowance exhausted.",
    )
    return pending("remote_work", employee_id, {"date": date})


@operation("attendance", write=True)
def request_attendance_correction(
    employee_id: str, date: str, corrected_time: str
) -> dict:
    """Request a check-in correction HH:MM without overwriting the original attendance."""
    self_access(employee_id)
    r = record(employee_id, date)
    clock(corrected_time)
    require(corrected_time != r["check_in"], "Check-in time is unchanged.")
    require(
        not r["check_out"] or corrected_time < r["check_out"],
        "Check-in must precede check-out.",
    )
    import json

    existing = rows(
        "SELECT payload FROM requests WHERE kind='attendance_correction' AND owner_id=? AND status='pending'",
        (employee_id,),
    )
    require(
        not any(json.loads(row["payload"])["date"] == date for row in existing),
        "Correction already pending for this date.",
        "conflict",
    )
    return pending(
        "attendance_correction",
        employee_id,
        {
            "date": date,
            "corrected_time": corrected_time,
            "reason": "Employee-reported incorrect check-in",
        },
    )
