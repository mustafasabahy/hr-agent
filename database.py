"""SQLite storage, UTC events and company-local calendar dates."""

import json
import os
import sqlite3
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
CONNECTION = ContextVar("connection", default=None)


def today():
    return datetime.now(ZoneInfo(os.getenv("COMPANY_TIMEZONE", "Europe/Berlin"))).date()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def connect():
    path = Path(os.getenv("COMPANY_DB_PATH", str(BASE_DIR / "data/company.db")))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db():
    conn = CONNECTION.get()
    if conn is None:
        raise RuntimeError("Service functions must run through execute()")
    return conn


def rows(sql, params=()):
    return [dict(row) for row in db().execute(sql, params).fetchall()]


def one(sql, params=()):
    row = db().execute(sql, params).fetchone()
    return dict(row) if row else None


def policy(key):
    result = one("SELECT value FROM settings WHERE key=?", (key,))
    if not result:
        raise ValueError(f"Missing demo policy: {key}")
    return json.loads(result["value"])


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS departments(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, min_staff INTEGER NOT NULL CHECK(min_staff>=0));
CREATE TABLE IF NOT EXISTS employees(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, department_id TEXT REFERENCES departments(id), role TEXT NOT NULL, manager_id TEXT REFERENCES employees(id), hire_date TEXT NOT NULL, status TEXT NOT NULL, phone TEXT DEFAULT '', preferred_name TEXT DEFAULT '', skills TEXT NOT NULL DEFAULT '[]', remote_allowed INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, employee_id TEXT REFERENCES employees(id), customer_id TEXT, roles TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies(id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, effective_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS holidays(day TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS leave_balances(employee_id TEXT REFERENCES employees(id), year INTEGER, annual_allowance INTEGER NOT NULL CHECK(annual_allowance>=0), PRIMARY KEY(employee_id,year));
CREATE TABLE IF NOT EXISTS leave_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT REFERENCES employees(id), start_date TEXT NOT NULL, end_date TEXT NOT NULL, days INTEGER NOT NULL CHECK(days>0), status TEXT NOT NULL, deducted_days INTEGER NOT NULL DEFAULT 0 CHECK(deducted_days>=0), reviewed_by TEXT, reviewed_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY, employee_id TEXT REFERENCES employees(id), day TEXT NOT NULL, check_in TEXT, check_out TEXT, UNIQUE(employee_id,day));
CREATE TABLE IF NOT EXISTS shifts(employee_id TEXT REFERENCES employees(id), day TEXT, start_time TEXT, end_time TEXT, PRIMARY KEY(employee_id,day));
CREATE TABLE IF NOT EXISTS timesheets(id INTEGER PRIMARY KEY, employee_id TEXT REFERENCES employees(id), day TEXT, hours REAL CHECK(hours>=0));
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, owner_id TEXT REFERENCES employees(id), payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, employee_id TEXT REFERENCES employees(id), customer_id TEXT, description TEXT NOT NULL, category TEXT, priority TEXT NOT NULL DEFAULT 'normal', status TEXT NOT NULL DEFAULT 'open', escalation_reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS courses(id TEXT PRIMARY KEY, title TEXT, prerequisites TEXT NOT NULL, capacity INTEGER CHECK(capacity>=0));
CREATE TABLE IF NOT EXISTS enrollments(course_id TEXT REFERENCES courses(id), employee_id TEXT REFERENCES employees(id), PRIMARY KEY(course_id,employee_id));
CREATE TABLE IF NOT EXISTS payslips(employee_id TEXT REFERENCES employees(id), month TEXT, gross_cents INTEGER CHECK(gross_cents>=0), deduction_cents INTEGER CHECK(deduction_cents>=0 AND deduction_cents<=gross_cents), PRIMARY KEY(employee_id,month));
CREATE TABLE IF NOT EXISTS inventory_items(id TEXT PRIMARY KEY, name TEXT UNIQUE, quantity INTEGER CHECK(quantity>=0), reorder_threshold INTEGER CHECK(reorder_threshold>=0), request_limit INTEGER CHECK(request_limit>0));
CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, employee_id TEXT REFERENCES employees(id), item_id TEXT REFERENCES inventory_items(id), warranty_end TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS software(name TEXT PRIMARY KEY, available INTEGER CHECK(available>=0));
CREATE TABLE IF NOT EXISTS licenses(software_name TEXT REFERENCES software(name), employee_id TEXT REFERENCES employees(id), PRIMARY KEY(software_name,employee_id));
CREATE TABLE IF NOT EXISTS purchase_orders(id TEXT PRIMARY KEY, item_id TEXT REFERENCES inventory_items(id), quantity INTEGER CHECK(quantity>0), expected_date TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, status TEXT NOT NULL, delivered_on TEXT, address TEXT NOT NULL, tracking_reference TEXT);
CREATE TABLE IF NOT EXISTS invoices(id TEXT PRIMARY KEY, vendor_id TEXT, invoice_number TEXT, amount_cents INTEGER CHECK(amount_cents>0), due_date TEXT, payment_status TEXT, UNIQUE(vendor_id,invoice_number));
CREATE TABLE IF NOT EXISTS budgets(department_id TEXT PRIMARY KEY REFERENCES departments(id), allocated_cents INTEGER CHECK(allocated_cents>=0), committed_cents INTEGER CHECK(committed_cents>=0), spent_cents INTEGER CHECK(spent_cents>=0 AND spent_cents+committed_cents<=allocated_cents));
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS project_members(project_id TEXT REFERENCES projects(id), employee_id TEXT REFERENCES employees(id), PRIMARY KEY(project_id,employee_id));
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT REFERENCES projects(id), assignee_id TEXT REFERENCES employees(id), title TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(project_id,assignee_id,title,due_date));
CREATE TABLE IF NOT EXISTS confirmations(id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, operation TEXT NOT NULL, arguments TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, result TEXT);
"""


def initialize():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute(
            "SELECT 1 FROM settings WHERE key='seed_version'"
        ).fetchone():
            from data.seed import seed

            seed(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    initialize()
    print("Company SQLite database initialized (existing data preserved).")
