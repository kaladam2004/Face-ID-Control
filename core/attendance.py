"""Attendance logging and duplicate prevention."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from core.config import DUPLICATE_TIMEOUT
from core.database import save_attendance_log, save_unknown_log, get_last_attendance_time
from core.recognition import save_frame, attendance_snapshot_path


class AttendanceManager:
    """Manages attendance logging with duplicate prevention."""

    def __init__(self):
        self.last_events: dict[int, float] = {}  # employee_id -> timestamp

    def log_recognized_employee(
        self,
        employee_id: int,
        employee_code: str,
        full_name: str,
        role: str,
        confidence: float,
        camera_ip: str,
        frame: Any,
        access_granted: bool
    ) -> dict[str, Any]:
        """Log attendance for recognized employee.

        Returns:
            Log result with status and message
        """
        current_time = time.time()

        # Check for duplicate within timeout
        if employee_id in self.last_events:
            time_diff = current_time - self.last_events[employee_id]
            if time_diff < DUPLICATE_TIMEOUT:
                return {
                    "status": "duplicate",
                    "message": f"Duplicate entry prevented for {full_name} ({DUPLICATE_TIMEOUT - time_diff:.0f}s remaining)",
                    "log_id": None,
                    "snapshot_path": None
                }

        # Take snapshot
        snapshot_path = save_frame(frame, attendance_snapshot_path(employee_id))

        # Determine status
        status = "GRANTED" if access_granted else "DENIED"

        # Save to database
        log_id = save_attendance_log(
            employee_id=employee_id,
            employee_code=employee_code,
            full_name=full_name,
            role=role,
            confidence=confidence,
            camera_ip=camera_ip,
            snapshot_path=snapshot_path,
            status=status,
            event_type="ENTRY"
        )

        # Update last event time
        self.last_events[employee_id] = current_time

        # Clean old entries (keep only recent)
        self._cleanup_old_entries()

        return {
            "status": status.lower(),
            "message": f"Attendance logged: {full_name} - {status}",
            "log_id": log_id,
            "snapshot_path": snapshot_path
        }

    def log_unknown_face(self, camera_ip: str, frame: Any) -> dict[str, Any]:
        """Log unknown face detection.

        Returns:
            Log result
        """
        # Take snapshot
        snapshot_path = save_frame(frame, attendance_snapshot_path(None, unknown=True))

        # Save to database
        log_id = save_unknown_log(
            camera_ip=camera_ip,
            snapshot_path=snapshot_path
        )

        return {
            "status": "unknown",
            "message": "Unknown face logged",
            "log_id": log_id,
            "snapshot_path": snapshot_path
        }

    def _cleanup_old_entries(self) -> None:
        """Remove old entries from memory cache."""
        current_time = time.time()
        cutoff_time = current_time - (DUPLICATE_TIMEOUT * 2)  # Keep 2x timeout

        to_remove = []
        for emp_id, timestamp in self.last_events.items():
            if timestamp < cutoff_time:
                to_remove.append(emp_id)

        for emp_id in to_remove:
            del self.last_events[emp_id]