"""Business logic for employee registration and recognition."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from core.database import save_employee, employee_code_exists, get_all_employees
from core.recognition import extract_faces, encoding_to_str, str_to_encoding, save_frame, employee_photo_path, face_engine_available, get_engine_error


def load_known_faces() -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    """Load known faces from database with metadata."""
    employees = get_all_employees()
    encodings: list[np.ndarray] = []
    meta: list[dict[str, Any]] = []

    for employee in employees:
        try:
            encodings.append(str_to_encoding(employee["face_encoding"]))
            meta.append(
                {
                    "id": employee["id"],
                    "employee_code": employee["employee_code"],
                    "full_name": employee["full_name"],
                    "role": employee["role"],
                }
            )
        except Exception as exc:
            print(f"[WARN] Failed to load encoding for employee #{employee['id']}: {exc}")

    return encodings, meta


def register_employee(full_name: str, employee_code: str, role: str, department: str | None, frame, skip_photo: bool = False) -> dict[str, Any]:
    """Register a new employee with face encoding."""
    full_name = full_name.strip()
    employee_code = employee_code.strip().upper()
    role = role.strip().lower()

    if not full_name or not employee_code or not role:
        return {"success": False, "message": "Full Name, Employee Code, and Role are required."}

    if not skip_photo and not face_engine_available():
        return {"success": False, "message": get_engine_error()}

    if employee_code_exists(employee_code):
        return {"success": False, "message": f"Employee Code '{employee_code}' already exists."}

    if skip_photo:
        # For bulk registration without photo
        photo_path = None
        encoding_str = None
    else:
        try:
            faces = extract_faces(frame)
        except Exception as exc:
            return {"success": False, "message": f"Face detection error: {exc}"}

        if len(faces) == 0:
            return {"success": False, "message": "No face detected in the frame. Please try again."}
        if len(faces) > 1:
            return {"success": False, "message": "Multiple faces detected. Only one person should be in the frame."}

        face = faces[0]
        photo_path = save_frame(frame, employee_photo_path(employee_code))
        encoding_str = encoding_to_str(face["encoding"])

    employee_id = save_employee(employee_code, full_name, role, department, photo_path, encoding_str)

    return {
        "success": True,
        "employee_id": employee_id,
        "message": f"✅ Employee '{full_name}' registered successfully with code {employee_code}.",
        "photo_path": photo_path,
    }
