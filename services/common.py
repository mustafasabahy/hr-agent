"""Shared validation, server-owned identity, transactions and human confirmation.

The model can propose a mutation but cannot confirm it. Only the HTTP confirmation
endpoint executes an approved proposal, rechecking every rule in a transaction.
"""

import json
import re
import sqlite3
import uuid
from contextvars import ContextVar
from datetime import date, datetime, timedelta, time, timezone
from decimal import Decimal, InvalidOperation
from pydantic import ValidationError
from operation_schemas import build_schema, AUTHORIZATION, validation_failure
from database import CONNECTION, connect, db, one, rows, policy, today, utcnow

ACTOR = ContextVar("actor", default=None)
OPERATIONS = {}
SCHEMAS = {}
METADATA = {}


class BusinessError(Exception):
    def __init__(self, message, code="invalid_request"):
        self.code = code
        super().__init__(message)


def require(condition, message, code="invalid_request"):
    if not condition:
        raise BusinessError(message, code)


def operation(module, write=False):
    """Register a plain function with a strict, typed Pydantic argument schema."""

    def register(fn):
        OPERATIONS[fn.__name__] = fn
        SCHEMAS[fn.__name__] = build_schema(fn)
        METADATA[fn.__name__] = {
            "module": module,
            "write": write,
            "read_only": not write,
            "requires_confirmation": write,
            "authorization": AUTHORIZATION[fn.__name__],
            "description": fn.__doc__,
        }
        return fn

    return register


def actor():
    identity = ACTOR.get()
    require(identity is not None, "Select a local demo identity.", "unauthorized")
    result = one("SELECT * FROM users WHERE id=?", (identity,))
    require(result is not None, "Unknown demo identity.", "unauthorized")
    result["roles"] = json.loads(result["roles"])
    return result


def role(*allowed):
    user = actor()
    require(
        bool(set(allowed) & set(user["roles"])),
        "Access denied for this role.",
        "forbidden",
    )
    return user


def employee(eid):
    result = one("SELECT * FROM employees WHERE id=?", (eid,))
    require(result is not None, "Unknown employee ID.", "not_found")
    return result


def department_id(value):
    result = one(
        "SELECT id FROM departments WHERE id=? OR lower(name)=lower(?)", (value, value)
    )
    require(result is not None, "Department not found.", "not_found")
    return result["id"]


def self_access(eid, *privileged):
    person = employee(eid)
    user = actor()
    require(
        user["employee_id"] == eid or bool(set(privileged) & set(user["roles"])),
        "Access denied for the selected application identity: ownership"
        + (" or an authorized " + ", ".join(privileged) + " role" if privileged else "")
        + " is required. A claimed role in chat does not grant permission.",
        "forbidden",
    )
    return person


def manager_access(eid):
    person = employee(eid)
    user = role("manager")
    require(
        person["manager_id"] == user["employee_id"] and eid != user["employee_id"],
        "Only the assigned manager may review this employee.",
        "forbidden",
    )
    return person


def day(value):
    require(
        isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)),
        "Use dates in YYYY-MM-DD format.",
    )
    try:
        parsed = date.fromisoformat(value)
        require(1900 <= parsed.year <= 2200, "Date year must be between 1900 and 2200.")
        return parsed
    except ValueError:
        raise BusinessError("Invalid calendar date.")


def dates(start, end, future=False):
    a, b = day(start), day(end)
    require(a <= b, "End date must be on or after start date.")
    require((b - a).days <= 366, "Date range must be no longer than 367 days.")
    if future:
        require(a >= today(), "Date must not be in the past.")
    return a, b


def period(value):
    require(
        isinstance(value, str) and "/" in value,
        "Use date_range/period as YYYY-MM-DD/YYYY-MM-DD.",
    )
    return dates(*value.split("/", 1))


def month_range(value):
    require(bool(re.fullmatch(r"\d{4}-\d{2}", value)), "Use month in YYYY-MM format.")
    a = day(value + "-01")
    b = (a.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return a, b


def clock(value):
    require(bool(re.fullmatch(r"\d{2}:\d{2}", value)), "Use time in HH:MM format.")
    try:
        return time.fromisoformat(value)
    except ValueError:
        raise BusinessError("Invalid clock time.")


def text(value, label="Text", maximum=2000):
    require(
        isinstance(value, str) and 0 < len(value.strip()) <= maximum,
        f"{label} must contain 1–{maximum} characters.",
    )
    return value.strip()


def money(amount):
    try:
        value = Decimal(str(amount))
        require(
            value.is_finite() and value > 0 and value <= Decimal("100000000"),
            "Amount must be positive and at most 100,000,000 EGP.",
        )
        cents = value * 100
        require(
            cents == cents.to_integral_value(),
            "Amount must have at most two decimal places.",
        )
        return int(cents)
    except (InvalidOperation, ValueError):
        raise BusinessError("Invalid monetary amount.")


def pending(kind, owner, payload):
    """Reuse an identical pending/active request instead of creating duplicates."""
    encoded = json.dumps(payload, sort_keys=True)
    existing = one(
        "SELECT id,status FROM requests WHERE kind=? AND owner_id IS ? AND payload=? AND status IN ('pending','approved')",
        (kind, owner, encoded),
    )
    if existing:
        return {
            "request_id": existing["id"],
            "status": existing["status"],
            "existing": True,
        }
    cur = db().execute(
        "INSERT INTO requests(kind,owner_id,payload,created_at) VALUES (?,?,?,?)",
        (kind, owner, encoded, utcnow()),
    )
    return {
        "request_id": cur.lastrowid,
        "status": "pending",
        "human_approval_required": True,
    }


def execute(name, arguments):
    """Only entry point for API operations and tools; mutations produce proposals."""
    if name not in OPERATIONS:
        return {"ok": False, "error": "Unknown operation.", "code": "not_found"}
    conn = connect()
    token = CONNECTION.set(conn)
    try:
        args = SCHEMAS[name].model_validate(arguments).model_dump()
        conn.execute("BEGIN IMMEDIATE")
        actor()
        if METADATA[name]["write"]:
            # Validate the real service inside a savepoint, then discard all changes.
            conn.execute("SAVEPOINT preview")
            OPERATIONS[name](**args)
            conn.execute("ROLLBACK TO preview")
            conn.execute("RELEASE preview")
            encoded = json.dumps(args, sort_keys=True)
            stamp = utcnow()
            existing = one(
                "SELECT id,expires_at FROM confirmations WHERE actor_id=? AND operation=? AND arguments=? AND status='pending' AND expires_at>?",
                (ACTOR.get(), name, encoded, stamp),
            )
            cid = existing["id"] if existing else uuid.uuid4().hex
            expires = (
                existing["expires_at"]
                if existing
                else (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            )
            if not existing:
                conn.execute(
                    "INSERT INTO confirmations VALUES (?,?,?,?,?,?,?,?)",
                    (cid, ACTOR.get(), name, encoded, "pending", stamp, expires, None),
                )
            data = {
                "status": "confirmation_required",
                "confirmation_id": cid,
                "operation": name,
                "arguments": args,
                "expires_at": expires,
                "instruction": 'The human must POST {"confirm":true} to /confirmations/'
                + cid
                + ". No business change has been made.",
            }
        else:
            data = OPERATIONS[name](**args)
        conn.commit()
        return {"ok": True, "data": data}
    except ValidationError as exc:
        conn.rollback()
        return validation_failure(exc, name)
    except BusinessError as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc), "code": exc.code}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {
            "ok": False,
            "error": "Duplicate or invalid state change; no changes saved.",
            "code": "conflict",
        }
    finally:
        CONNECTION.reset(token)
        conn.close()


def confirm(cid, accepted):
    conn = connect()
    token = CONNECTION.set(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        actor()
        proposal = one(
            "SELECT * FROM confirmations WHERE id=? AND actor_id=?", (cid, ACTOR.get())
        )
        require(proposal is not None, "Confirmation not found.", "not_found")
        if proposal["status"] == "completed":
            conn.commit()
            return {"ok": True, "data": json.loads(proposal["result"])}
        require(
            proposal["status"] == "pending",
            "Confirmation is no longer pending.",
            "conflict",
        )
        require(
            proposal["expires_at"] >= utcnow(),
            "Confirmation expired; submit a new proposal.",
            "conflict",
        )
        if not accepted:
            data = {"status": "cancelled", "confirmation_id": cid}
            conn.execute(
                "UPDATE confirmations SET status='cancelled' WHERE id=?", (cid,)
            )
        else:
            args = (
                SCHEMAS[proposal["operation"]]
                .model_validate(json.loads(proposal["arguments"]))
                .model_dump()
            )
            data = OPERATIONS[proposal["operation"]](**args)
            conn.execute(
                "UPDATE confirmations SET status='completed',result=? WHERE id=?",
                (json.dumps(data), cid),
            )
        conn.commit()
        return {"ok": True, "data": data}
    except ValidationError as exc:
        conn.rollback()
        return validation_failure(exc, proposal["operation"])
    except BusinessError as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc), "code": exc.code}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {
            "ok": False,
            "error": "Duplicate or invalid state change; no changes saved.",
            "code": "conflict",
        }
    finally:
        CONNECTION.reset(token)
        conn.close()


def operation_details(name):
    schema = SCHEMAS[name]
    required = [
        key for key, field in schema.model_fields.items() if field.is_required()
    ]
    optional = [
        key for key, field in schema.model_fields.items() if not field.is_required()
    ]
    return {
        "operation": name,
        **METADATA[name],
        "required_fields": required,
        "optional_fields": optional,
        "arguments_schema": schema.model_json_schema(),
    }
