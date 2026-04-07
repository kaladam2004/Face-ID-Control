"""Business logic for employee registration and turnstile recognition."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np

import database as db
import face_utils as fu

ANTI_DUPLICATE_SECONDS = 30


def load_known_faces() -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    employees = db.get_all_employees()
    encodings: list[np.ndarray] = []
    meta: list[dict[str, Any]] = []

    for employee in employees:
        try:
            encodings.append(fu.str_to_encoding(employee["face_encoding"]))
            meta.append(
                {
                    "employee_id": employee["id"],
                    "full_name": employee["full_name"],
                    "employee_code": employee["employee_code"],
                }
            )
        except Exception as exc:
            print(f"[WARN] Failed to load encoding for employee #{employee['id']}: {exc}")

    return encodings, meta


def register_employee(full_name: str, employee_code: str, frame) -> dict[str, Any]:
    full_name = full_name.strip()
    employee_code = employee_code.strip().upper()

    if not full_name or not employee_code:
        return {"success": False, "message": "Full Name ва Employee Code ҳатмӣ мебошанд."}

    if not fu.face_engine_available():
        return {"success": False, "message": fu.get_engine_error()}

    if db.employee_code_exists(employee_code):
        return {"success": False, "message": f"Employee Code '{employee_code}' аллакай мавҷуд аст."}

    try:
        faces = fu.extract_faces(frame)
    except Exception as exc:
        return {"success": False, "message": f"Хатогии face detection: {exc}"}

    if len(faces) == 0:
        return {"success": False, "message": "Дар кадр рӯй ёфт нашуд. Лутфан дубора кӯшиш кунед."}
    if len(faces) > 1:
        return {"success": False, "message": "Дар кадр зиёда аз як рӯй ҳаст. Танҳо як нафар бояд бошад."}

    face = faces[0]
    photo_path = fu.save_frame(frame, fu.employee_photo_path(employee_code))
    encoding_str = fu.encoding_to_str(face["encoding"])
    employee_id = db.save_employee(full_name, employee_code, photo_path, encoding_str)

    return {
        "success": True,
        "employee_id": employee_id,
        "message": f"✅ Корманд '{full_name}' бо рамзи {employee_code} бомуваффақият сабт шуд.",
        "photo_path": photo_path,
    }


def process_turnstile_frame(frame) -> dict[str, Any]:
    if not fu.face_engine_available():
        return _result("error", fu.get_engine_error())

    known_encodings, known_meta = load_known_faces()
    if not known_encodings:
        return _result("error", "Ҳанӯз ягон корманд сабт нашудааст.")

    try:
        faces = fu.extract_faces(frame)
    except Exception as exc:
        return _result("error", f"Хатогии face detection: {exc}")

    if len(faces) == 0:
        return _result("no_face", "Дар кадр рӯй ёфт нашуд.")
    if len(faces) > 1:
        return _result("multiple_faces", "Дар кадр зиёда аз як рӯй ҳаст. Барои турникет танҳо як нафар истад.")

    face = faces[0]
    match = fu.compare_face(face["encoding"], known_encodings, known_meta)
    event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if match["recognized"]:
        employee_id = match["employee_id"]
        full_name = match["full_name"]
        last_log_time = db.get_last_log_time(employee_id)
        if last_log_time:
            last_dt = datetime.strptime(last_log_time, "%Y-%m-%d %H:%M:%S")
            if datetime.now() - last_dt < timedelta(seconds=ANTI_DUPLICATE_SECONDS):
                return {
                    "status": "duplicate",
                    "message": f"⚠ {full_name} дар {ANTI_DUPLICATE_SECONDS} сонияи охир аллакай сабт шудааст.",
                    "full_name": full_name,
                    "event_time": event_time,
                    "confidence": match["confidence"],
                    "snapshot_path": None,
                }

        snapshot_path = fu.save_frame(frame, fu.log_snapshot_path(employee_id=employee_id, unknown=False))
        db.save_log(
            employee_id=employee_id,
            full_name=full_name,
            event_type="IN",
            event_time=event_time,
            confidence=match["confidence"],
            image_path=snapshot_path,
        )
        return {
            "status": "granted",
            "message": f"✅ Access Granted — {full_name}",
            "full_name": full_name,
            "event_time": event_time,
            "confidence": match["confidence"],
            "snapshot_path": snapshot_path,
        }

    snapshot_path = fu.save_frame(frame, fu.log_snapshot_path(unknown=True))
    db.save_log(
        employee_id=None,
        full_name="Unknown Person",
        event_type="IN",
        event_time=event_time,
        confidence=match["confidence"],
        image_path=snapshot_path,
    )
    return {
        "status": "denied",
        "message": "🚫 Unknown Person",
        "full_name": "Unknown Person",
        "event_time": event_time,
        "confidence": match["confidence"],
        "snapshot_path": snapshot_path,
    }


def _result(status: str, message: str) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "full_name": "",
        "event_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "confidence": 0.0,
        "snapshot_path": None,
    }
