"""Member-scoped project tasks and deterministic progress counts."""

from datetime import timedelta
from database import db, one, rows, policy, today
from services.common import (
    operation,
    require,
    actor,
    role,
    employee,
    day,
    dates,
    period,
    text,
)


def access(project_id):
    user = actor()
    require(user["employee_id"] is not None, "Employee identity required.", "forbidden")
    project = one(
        "SELECT id FROM projects WHERE id=? OR lower(name)=lower(?)",
        (project_id, project_id),
    )
    require(project is not None, "Project not found.", "not_found")
    project_id = project["id"]
    require(
        one(
            "SELECT 1 FROM project_members WHERE project_id=? AND employee_id=?",
            (project_id, user["employee_id"]),
        )
        is not None,
        "Project membership required.",
        "forbidden",
    )
    user["project_id"] = project_id
    return user


@operation("projects", write=True)
def create_project_task(
    project_id: str, assignee_id: str, title: str, due_date: str
) -> dict:
    """Project member creates a task for an active member with a present/future due date."""
    project_id = access(project_id)["project_id"]
    p = employee(assignee_id)
    require(p["status"] == "active", "Assignee must be active.")
    require(
        one(
            "SELECT 1 FROM project_members WHERE project_id=? AND employee_id=?",
            (project_id, assignee_id),
        )
        is not None,
        "Assignee is not a project member.",
    )
    dates(due_date, due_date, True)
    title = text(title, "Task title", 200)
    require(
        not one(
            "SELECT id FROM tasks WHERE project_id=? AND assignee_id=? AND title=? AND due_date=?",
            (project_id, assignee_id, title, due_date),
        ),
        "Identical task already exists.",
        "conflict",
    )
    cur = db().execute(
        "INSERT INTO tasks(project_id,assignee_id,title,due_date,status) VALUES (?,?,?,?,?)",
        (project_id, assignee_id, title, due_date, "pending"),
    )
    return {
        "task_id": cur.lastrowid,
        "status": "pending",
        "assignee_id": assignee_id,
        "due_date": due_date,
    }


@operation("projects")
def get_overdue_tasks(project_id: str) -> dict:
    """Project member retrieves incomplete tasks due before company-local today."""
    project_id = access(project_id)["project_id"]
    return {
        "tasks": rows(
            "SELECT * FROM tasks WHERE project_id=? AND status!='completed' AND due_date<?",
            (project_id, str(today())),
        )
    }


@operation("projects")
def check_task_deadline_conflicts(employee_id: str, date_range: str) -> dict:
    """Self or assigned manager finds incomplete deadlines close together; date_range: start/end."""
    user = actor()
    p = employee(employee_id)
    require(
        user["employee_id"] == employee_id
        or ("manager" in user["roles"] and p["manager_id"] == user["employee_id"]),
        "Access denied to employee task load.",
        "forbidden",
    )
    a, b = period(date_range)
    tasks = rows(
        "SELECT * FROM tasks WHERE assignee_id=? AND status!='completed' AND due_date BETWEEN ? AND ? ORDER BY due_date",
        (employee_id, str(a), str(b)),
    )
    # Managers must also belong to the project, preventing cross-project leakage.
    tasks = [
        t
        for t in tasks
        if one(
            "SELECT 1 FROM project_members WHERE project_id=? AND employee_id=?",
            (t["project_id"], user["employee_id"]),
        )
    ]
    window = policy("deadline_window_days")
    pairs = []
    for i, t in enumerate(tasks):
        for other in tasks[i + 1 :]:
            if (day(other["due_date"]) - day(t["due_date"])).days <= window:
                pairs.append(
                    {
                        "task_ids": [t["id"], other["id"]],
                        "due_dates": [t["due_date"], other["due_date"]],
                    }
                )
    return {
        "potential_conflicts": pairs,
        "window_days": window,
        "note": "Scheduling signal only; no conclusion about employee capability.",
    }


@operation("projects", write=True)
def update_task_status(task_id: int, status: str) -> dict:
    """Assignee or assigned project manager updates pending→in_progress/completed or in_progress→completed."""
    require(task_id > 0, "Task ID must be positive.")
    r = one("SELECT * FROM tasks WHERE id=?", (task_id,))
    require(r is not None, "Task not found.", "not_found")
    user = access(r["project_id"])
    assignee = employee(r["assignee_id"])
    require(
        user["employee_id"] == r["assignee_id"]
        or (
            "manager" in user["roles"] and assignee["manager_id"] == user["employee_id"]
        ),
        "Only assignee or assigned project manager can update task.",
        "forbidden",
    )
    transitions = {
        "pending": ["in_progress", "completed"],
        "in_progress": ["completed"],
        "completed": [],
    }
    require(
        status in transitions.get(r["status"], []),
        "Invalid or repeated task status transition.",
        "conflict",
    )
    db().execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
    return {"task_id": task_id, "old_status": r["status"], "new_status": status}


@operation("projects")
def get_project_progress(project_id: str) -> dict:
    """Project member receives computed total, completed, pending, in-progress and overdue counts."""
    project_id = access(project_id)["project_id"]
    tasks = rows("SELECT status,due_date FROM tasks WHERE project_id=?", (project_id,))
    completed = sum(t["status"] == "completed" for t in tasks)
    return {
        "project_id": project_id,
        "total": len(tasks),
        "completed": completed,
        "pending": sum(t["status"] == "pending" for t in tasks),
        "in_progress": sum(t["status"] == "in_progress" for t in tasks),
        "overdue": sum(
            t["status"] != "completed" and day(t["due_date"]) < today() for t in tasks
        ),
        "completion_percent": round(completed / len(tasks) * 100, 2) if tasks else 0,
    }
