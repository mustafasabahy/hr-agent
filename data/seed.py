"""Fictional fixtures, inserted only once; dates relative to company-local today."""

import json
from datetime import timedelta
from database import BASE_DIR, today, utcnow


def seed(c):
    now = today()
    year = now.year
    settings = {
        "seed_version": 1,
        "annual_allowance": 30,
        "weekends": [5, 6],
        "eligibility_days": 90,
        "probation_days": 180,
        "carryover_limit": 5,
        "carryover_expiry_month": 3,
        "carryover_expiry_day": 31,
        "schedule_start": "09:00",
        "schedule_end": "17:00",
        "grace_minutes": 10,
        "daily_hours": 8,
        "max_overtime_hours": 4,
        "remote_days_month": 8,
        "expense_limit_cents": 500000,
        "expense_categories": ["travel", "equipment", "training"],
        "return_window_days": 14,
        "return_exceptions": {"ORD-OLD": 30},
        "deadline_window_days": 1,
        "document_types": ["employment_verification", "salary_certificate"],
        "onboarding_tasks": ["HR orientation", "IT setup", "Policy acknowledgement"],
        "offboarding_tasks": ["HR review", "Asset return", "Access review by IT"],
    }
    c.executemany(
        "INSERT INTO settings VALUES (?,?)",
        [(k, json.dumps(v)) for k, v in settings.items()],
    )
    c.executemany(
        "INSERT INTO departments VALUES (?,?,?)",
        [
            ("ENG", "Engineering", 1),
            ("HR", "Human Resources", 1),
            ("FIN", "Finance", 1),
        ],
    )
    people = json.loads((BASE_DIR / "employees.json").read_text())
    department_ids = {"Engineering": "ENG", "Human Resources": "HR", "Finance": "FIN"}
    # Keep all three original names, departments and roles.
    for employee_id, p in zip(["E001", "E002", "E003"], people):
        c.execute(
            "INSERT INTO employees(id,name,department_id,role,hire_date,status,skills) VALUES (?,?,?,?,?,?,?)",
            (
                employee_id,
                p["name"],
                department_ids[p["department"]],
                p["role"],
                str(now - timedelta(days=400)),
                "active",
                '["python_basics"]',
            ),
        )
    for eid, name, dept, role in [
        ("E004", "Nadia", "ENG", "Engineering Manager"),
        ("E005", "Youssef", "HR", "HR Manager"),
        ("E006", "Mona", "FIN", "Finance Manager"),
    ]:
        c.execute(
            "INSERT INTO employees(id,name,department_id,role,hire_date,status) VALUES (?,?,?,?,?,?)",
            (eid, name, dept, role, str(now - timedelta(days=900)), "active"),
        )
    c.executemany(
        "UPDATE employees SET manager_id=? WHERE id=?",
        [("E004", "E001"), ("E005", "E002"), ("E006", "E003")],
    )
    c.execute(
        "INSERT INTO employees(id,name,department_id,role,hire_date,status,remote_allowed) VALUES (?,?,?,?,?,?,?)",
        (
            "E007",
            "New Starter",
            "ENG",
            "Intern",
            str(now - timedelta(days=10)),
            "active",
            0,
        ),
    )
    users = [
        ("ahmed", "E001", None, ["employee"]),
        ("sara", "E002", None, ["employee", "hr"]),
        ("lina", "E003", None, ["employee", "finance", "payroll"]),
        ("nadia", "E004", None, ["employee", "manager"]),
        ("youssef", "E005", None, ["employee", "hr", "manager"]),
        ("mona", "E006", None, ["employee", "finance", "payroll", "manager"]),
        ("new-starter", "E007", None, ["employee"]),
        ("customer-1", None, "C001", ["customer"]),
        ("customer-2", None, "C002", ["customer"]),
    ]
    c.executemany(
        "INSERT INTO users VALUES (?,?,?,?)",
        [(u, e, cu, json.dumps(r)) for u, e, cu, r in users],
    )
    for (eid,) in c.execute("SELECT id FROM employees").fetchall():
        for y in [year - 1, year, year + 1]:
            c.execute("INSERT INTO leave_balances VALUES (?,?,?)", (eid, y, 30))
    c.executemany(
        "INSERT INTO policies VALUES (?,?,?,?)",
        [
            (
                "annual",
                "Annual leave",
                "30 days per year after 90 days of active employment. Weekends and company holidays excluded. Manager approval and team coverage required.",
                "2026-01-01",
            ),
            (
                "remote",
                "Remote work",
                "Eligible employees may request up to 8 remote days per calendar month. Requests require human approval.",
                "2026-01-01",
            ),
            (
                "carryover",
                "Leave carryover",
                "At most 5 unused days may be carried to next year, expiring March 31. This demo calculates eligibility only.",
                "2026-01-01",
            ),
        ],
    )
    for y in [year, year + 1]:
        c.execute(
            "INSERT INTO holidays VALUES (?,?)",
            (f"{y}-12-25", "Company winter holiday"),
        )
    workday = now - timedelta(days=1)
    while workday.weekday() > 4:
        workday -= timedelta(days=1)
    for eid in ["E001", "E002", "E003"]:
        c.execute(
            "INSERT INTO attendance(employee_id,day,check_in,check_out) VALUES (?,?,?,?)",
            (eid, str(workday), "09:25", None if eid == "E002" else "20:00"),
        )
        c.execute(
            "INSERT INTO timesheets(employee_id,day,hours) VALUES (?,?,?)",
            (eid, str(workday), 8),
        )
    # A deliberate duplicate timesheet for validation demos.
    c.execute(
        "INSERT INTO timesheets(employee_id,day,hours) VALUES (?,?,?)",
        ("E001", str(workday), 8),
    )
    nextday = now + timedelta(days=1)
    for offset in range(35):
        day = nextday + timedelta(days=offset)
        if day.weekday() < 5:
            for eid in ["E001", "E002", "E003", "E004", "E005", "E006", "E007"]:
                c.execute(
                    "INSERT INTO shifts VALUES (?,?,?,?)",
                    (eid, str(day), "09:00", "17:00"),
                )
    c.execute(
        "INSERT INTO courses VALUES (?,?,?,?)",
        ("PYTHON", "Python training", '["python_basics"]', 3),
    )
    c.execute(
        "INSERT INTO courses VALUES (?,?,?,?)",
        ("FULL", "Full training course", "[]", 0),
    )
    for eid in ["E001", "E002", "E003"]:
        c.execute(
            "INSERT INTO payslips VALUES (?,?,?,?)",
            (eid, f"{year}-09", 2000000, 200000),
        )
    c.executemany(
        "INSERT INTO inventory_items VALUES (?,?,?,?,?)",
        [("LAPTOP", "laptops", 10, 3, 5), ("MOUSE", "mice", 2, 5, 10)],
    )
    c.execute(
        "INSERT INTO assets VALUES (?,?,?,?)",
        ("ASSET-1", "E001", "LAPTOP", str(now + timedelta(days=60))),
    )
    c.execute(
        "INSERT INTO assets VALUES (?,?,?,?)",
        ("ASSET-2", "E002", "LAPTOP", str(now - timedelta(days=1))),
    )
    c.executemany(
        "INSERT INTO software VALUES (?,?)",
        [("Microsoft Office", 3), ("Unavailable Suite", 0)],
    )
    c.execute(
        "INSERT INTO purchase_orders VALUES (?,?,?,?,?)",
        ("PO-1", "LAPTOP", 10, str(now + timedelta(days=7)), "pending"),
    )
    c.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?)",
        [
            (
                "ORD-1",
                "C001",
                "delivered",
                str(now - timedelta(days=5)),
                "Fictional address 1",
                "TRACK-DEMO-1",
            ),
            ("ORD-2", "C001", "processing", None, "Fictional address 2", None),
            (
                "ORD-OLD",
                "C001",
                "delivered",
                str(now - timedelta(days=20)),
                "Fictional address 3",
                "TRACK-DEMO-3",
            ),
            (
                "ORD-EXPIRED",
                "C002",
                "delivered",
                str(now - timedelta(days=20)),
                "Fictional address 4",
                "TRACK-DEMO-4",
            ),
        ],
    )
    c.execute(
        "INSERT INTO tickets(kind,customer_id,description,created_at) VALUES (?,?,?,?)",
        ("customer", "C001", "Fictional delayed delivery", utcnow()),
    )
    c.executemany(
        "INSERT INTO invoices VALUES (?,?,?,?,?,?)",
        [
            ("INV-100", "V001", "100", 100000, str(now - timedelta(days=10)), "paid"),
            ("INV-101", "V001", "101", 200000, str(now - timedelta(days=5)), "unpaid"),
        ],
    )
    for dept in ["ENG", "HR", "FIN"]:
        c.execute(
            "INSERT INTO budgets VALUES (?,?,?,?)", (dept, 10000000, 2000000, 3000000)
        )
    c.execute("INSERT INTO projects VALUES (?,?)", ("ALPHA", "Project Alpha"))
    c.executemany(
        "INSERT INTO project_members VALUES (?,?)",
        [("ALPHA", e) for e in ["E001", "E002", "E004"]],
    )
    c.executemany(
        "INSERT INTO tasks(project_id,assignee_id,title,due_date,status) VALUES (?,?,?,?,?)",
        [
            (
                "ALPHA",
                "E001",
                "Prepare report",
                str(now - timedelta(days=2)),
                "pending",
            ),
            (
                "ALPHA",
                "E001",
                "Review report",
                str(now - timedelta(days=2)),
                "in_progress",
            ),
            ("ALPHA", "E002", "HR overview", str(now + timedelta(days=5)), "completed"),
        ],
    )
