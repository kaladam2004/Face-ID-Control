"""Role-based access control system."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from core.config import WORK_HOURS_START, WORK_HOURS_END, SCHOOL_HOURS_START, SCHOOL_HOURS_END


def check_access(role: str, current_time: datetime | None = None) -> bool:
    """Check if access is allowed for the given role at current time.

    Args:
        role: Employee role (teacher, assistant, security, reception, staff)
        current_time: Time to check (defaults to now)

    Returns:
        True if access is granted, False otherwise
    """
    if current_time is None:
        current_time = datetime.now()

    current_t = current_time.time()

    # Security has 24/7 access
    if role == "security":
        return True

    # Teacher access during school hours
    elif role == "teacher":
        school_start = time.fromisoformat(SCHOOL_HOURS_START)
        school_end = time.fromisoformat(SCHOOL_HOURS_END)
        return school_start <= current_t <= school_end

    # Assistant access during work hours
    elif role == "assistant":
        work_start = time.fromisoformat(WORK_HOURS_START)
        work_end = time.fromisoformat(WORK_HOURS_END)
        return work_start <= current_t <= work_end

    # Reception access during work hours
    elif role == "reception":
        work_start = time.fromisoformat(WORK_HOURS_START)
        work_end = time.fromisoformat(WORK_HOURS_END)
        return work_start <= current_t <= work_end

    # Staff access during work hours (customize as needed)
    elif role == "staff":
        work_start = time.fromisoformat(WORK_HOURS_START)
        work_end = time.fromisoformat(WORK_HOURS_END)
        return work_start <= current_t <= work_end

    # Unknown role - deny access
    else:
        return False


def get_access_message(role: str, allowed: bool) -> str:
    """Get human-readable access message."""
    if allowed:
        return f"ACCESS GRANTED - {role.title()}"
    else:
        return f"ACCESS DENIED - {role.title()} not allowed at this time"


def get_role_schedule(role: str) -> str:
    """Get schedule description for a role."""
    schedules = {
        "security": "24/7 access",
        "teacher": f"School hours ({SCHOOL_HOURS_START} - {SCHOOL_HOURS_END})",
        "assistant": f"Work hours ({WORK_HOURS_START} - {WORK_HOURS_END})",
        "reception": f"Work hours ({WORK_HOURS_START} - {WORK_HOURS_END})",
        "staff": f"Work hours ({WORK_HOURS_START} - {WORK_HOURS_END})"
    }
    return schedules.get(role, "No schedule defined")