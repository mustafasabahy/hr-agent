"""Narrow provenance guard for years in natural-language agent requests.

This does not route intents or generate fake replies. It blocks tool dispatch if
calendar arguments invent an absent year. Explicit canonical HTTP operation
arguments remain independent of natural language and use normal schemas.
"""

import calendar
import re
import unicodedata
from contextvars import ContextVar
from datetime import timedelta
from database import today

USER_MESSAGE = ContextVar("user_message", default=None)
USER_HISTORY = ContextVar("user_history", default=None)


def active_years(message, history):
    """Conservative provenance, never a union of years from the whole thread."""

    def years(text):
        return set(re.findall(r"(?<!\d)(?:19|20|21|22)\d{2}(?!\d)", normalized(text)))

    explicit = years(message)
    if explicit:
        return explicit if len(explicit) == 1 else set()
    if re.search(r"\b(?:this|current) (?:year|month|week)\b|\b(?:today|tomorrow|yesterday)\b|هذه السنة|هذا العام", normalized(message)):
        # Current relative context overrides an older explicit calendar year.
        # calendar_guard validates these against the trusted local date below.
        return set()
    reference = r"\b(that|those|this|it|earlier|just|period|same|latest|how many|what.*status|what.*balance)\b|الفترة|السنة دي"
    if not re.search(reference, normalized(message)):
        return set()
    for old in reversed(history):
        found = years(old)
        if found:
            if re.search(
                r"\b(invoice|payslip|salary|ticket|order|project|laptop|inventory|expense)\b",
                normalized(old),
            ):
                return set()  # A month in another business topic is not leave context.
            relevant = re.search(
                r"\b(leave|vacation|annual|january|february|march|april|may|june|july|august|september|october|november|december)\b|\d{4}-\d{2}-\d{2}|إجازة|اجازة",
                normalized(old),
            )
            return found if relevant and len(found) == 1 else set()
        if not re.search(reference, normalized(old)):
            return set()
    return set()


def normalized(value):
    return "".join(
        str(unicodedata.digit(c)) if c.isdigit() else c for c in value.casefold()
    )


def calendar_guard(arguments):
    message = USER_MESSAGE.get()
    if message is None:
        return None  # Explicit programmatic/API args, not an NL request.
    message = normalized(message)
    history = USER_HISTORY.get()
    years = (
        active_years(message, history)
        if history is not None
        else set(re.findall(r"(?<!\d)(?:19|20|21|22)\d{2}(?!\d)", message))
    )
    now = today()
    relative_days = set()
    for pattern, offset in [
        (r"\btoday\b|النهارده|النهاردة|اليوم", 0),
        (r"\btomorrow\b|بكرة|بكره|غدا|غدًا", 1),
        (r"\byesterday\b|امبارح|أمس|امس", -1),
    ]:
        if re.search(pattern, message):
            relative_days.add(str(now + timedelta(days=offset)))
    current_year = bool(
        re.search(
            r"\b(?:this|current) year\b|السنة دي|السنه دي|هذه السنة|هذا العام", message
        )
    )
    current_month = bool(
        re.search(r"\b(?:this|current) month\b|الشهر ده|هذا الشهر", message)
    )
    current_week = bool(
        re.search(
            r"\b(?:this|current) week\b|الأسبوع ده|الاسبوع ده|هذا الأسبوع", message
        )
    )
    relative_periods = set()
    if current_week:
        first = now - timedelta(days=now.weekday())
        last = first + timedelta(days=6)
        relative_periods.add((str(first), str(last)))
    if current_month:
        first = now.replace(day=1)
        last = now.replace(day=calendar.monthrange(now.year, now.month)[1])
        relative_periods.add((str(first), str(last)))
    for field, value in arguments.items():
        if value is None:
            continue
        if field == "year":
            missing = str(value) not in years and not (
                current_year and value == now.year
            )
        elif field == "month":
            missing = value[:4] not in years and not (
                current_month and value == now.strftime("%Y-%m")
            )
        elif field in {"date_range", "period"}:
            parts = tuple(value.split("/"))
            missing = (
                any(part[:4] not in years for part in parts)
                and parts not in relative_periods
            )
        elif field in {
            "date",
            "shift_date",
            "due_date",
            "start_date",
            "end_date",
            "new_start_date",
            "new_end_date",
        }:
            missing = value[:4] not in years and value not in relative_days
        else:
            continue
        if missing:
            return {
                "ok": False,
                "code": "clarification_required",
                "error": "The calendar year was not supplied by the user for this date. No business operation was executed.",
                "missing_fields": ["year"],
                "errors": [
                    {
                        "field": field,
                        "type": "missing_year_context",
                        "message": "Ask which calendar year; never infer it from the application date.",
                    }
                ],
                "clarification_required": True,
                "next_step": "Ask the user for the explicit year and a complete restatement of the request. Do not retry a business operation with a guessed year.",
            }
    return None
