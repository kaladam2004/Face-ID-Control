"""Face recognition utilities (extended from face_utils)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    import face_recognition
except Exception:
    face_recognition = None

from core.config import CONFIDENCE_THRESHOLD, PHOTOS_DIR, LOGS_DIR, UNKNOWN_DIR
from core.liveness import is_face_live


def face_engine_available() -> bool:
    try:
        import face_recognition
        # Try a simple operation to check if it's working
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        face_recognition.face_locations(test_image)
        return True
    except Exception:
        return False


def get_engine_error() -> str:
    return (
        "face_recognition module not available. "
        "Install requirements for your platform."
    )


def ensure_directories() -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    UNKNOWN_DIR.mkdir(parents=True, exist_ok=True)


def encoding_to_str(encoding: np.ndarray) -> str:
    return json.dumps(encoding.tolist())


def str_to_encoding(encoding_str: str) -> np.ndarray:
    return np.asarray(json.loads(encoding_str), dtype=np.float64)


def extract_faces(frame: np.ndarray) -> list[dict[str, Any]]:
    if face_recognition is None:
        raise RuntimeError(get_engine_error())

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model="hog")
    encodings = face_recognition.face_encodings(rgb, locations)

    faces: list[dict[str, Any]] = []
    for location, encoding in zip(locations, encodings):
        top, right, bottom, left = location
        faces.append(
            {
                "location": location,
                "encoding": encoding,
                "box": (left, top, right, bottom),
            }
        )
    return faces


def compare_face(
    face_encoding: np.ndarray,
    known_encodings: list[np.ndarray],
    known_meta: list[dict[str, Any]],
    frame: np.ndarray | None = None,
    face_location: tuple[int, int, int, int] | None = None,
    check_liveness: bool = False,
) -> dict[str, Any]:
    """Compare face encoding with known faces and optionally check liveness.

    Args:
        face_encoding: Face encoding to compare
        known_encodings: List of known face encodings
        known_meta: Metadata for known faces
        frame: Optional frame for liveness detection
        face_location: Optional face location for liveness detection
        check_liveness: Whether to perform liveness detection

    Returns:
        Recognition result with optional liveness info
    """
    if not known_encodings:
        result = {
            "recognized": False,
            "employee_id": None,
            "employee_code": None,
            "full_name": "Unknown Person",
            "role": None,
            "confidence": 0.0,
            "distance": 1.0,
        }
        if check_liveness:
            result["is_live"] = False
            result["liveness_confidence"] = 0.0
            result["liveness_reason"] = "No known faces to compare"
        return result

    distances = face_recognition.face_distance(known_encodings, face_encoding)
    best_idx = int(np.argmin(distances))
    best_distance = float(distances[best_idx])
    confidence = max(0.0, min(1.0, 1.0 - best_distance))
    best_person = known_meta[best_idx]

    result = {
        "recognized": confidence >= CONFIDENCE_THRESHOLD,
        "employee_id": best_person["id"] if confidence >= CONFIDENCE_THRESHOLD else None,
        "employee_code": best_person["employee_code"] if confidence >= CONFIDENCE_THRESHOLD else None,
        "full_name": best_person["full_name"] if confidence >= CONFIDENCE_THRESHOLD else "Unknown Person",
        "role": best_person["role"] if confidence >= CONFIDENCE_THRESHOLD else None,
        "confidence": confidence,
        "distance": best_distance,
    }

    # Add liveness detection if requested
    if check_liveness and frame is not None and face_location is not None:
        face_data = {
            "location": face_location,
            "encoding": face_encoding,
            "box": face_location,
        }
        liveness_result = is_face_live(frame, face_data)
        result.update({
            "is_live": liveness_result["is_live"],
            "liveness_confidence": liveness_result["confidence"],
            "liveness_reason": liveness_result["reason"],
        })

        # If liveness check fails, mark as unrecognized even if face matches
        if not liveness_result["is_live"]:
            result.update({
                "recognized": False,
                "employee_id": None,
                "employee_code": None,
                "full_name": "Spoofed/Photo Detected",
                "role": None,
                "confidence": 0.0,
            })

    return result


def annotate_frame(
    frame: np.ndarray,
    faces: list[dict[str, Any]],
    known_encodings: list[np.ndarray] | None = None,
    known_meta: list[dict[str, Any]] | None = None,
) -> np.ndarray:
    display = frame.copy()
    known_encodings = known_encodings or []
    known_meta = known_meta or []

    for face in faces:
        left, top, right, bottom = face["box"]
        label = "Face"
        color = (52, 152, 219)  # Blue for unknown

        if known_encodings and known_meta:
            match = compare_face(face["encoding"], known_encodings, known_meta)
            if match["recognized"]:
                # Check access status from face data
                access_status = face.get("access_status", "granted")
                if access_status == "granted":
                    color = (34, 197, 94)  # Green
                    label = f"✓ {match['full_name']} ({match['role']}) {match['confidence']:.0%}"
                elif access_status == "denied":
                    color = (245, 158, 11)  # Yellow/Orange
                    label = f"⚠ {match['full_name']} ({match['role']}) - ACCESS DENIED"
                else:
                    color = (239, 68, 68)  # Red
                    label = f"✗ {match['full_name']} ({match['role']})"
            else:
                color = (239, 68, 68)  # Red
                label = f"✗ Unknown ({match['confidence']:.0%})"
        else:
            if len(faces) == 1:
                label = "1 face detected"
                color = (34, 197, 94)
            elif len(faces) > 1:
                label = f"{len(faces)} faces"
                color = (245, 158, 11)
            else:
                label = "No face"

        cv2.rectangle(display, (left, top), (right, bottom), color, 2)
        text_y = max(24, top - 10)
        cv2.putText(
            display,
            label,
            (left, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )

    return display


def save_frame(frame: np.ndarray, target_path: Path) -> str:
    ensure_directories()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(target_path), frame)
    return str(target_path)


def employee_photo_path(employee_code: str) -> Path:
    safe_code = "".join(ch for ch in employee_code if ch.isalnum() or ch in ("-", "_")) or "EMP"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return PHOTOS_DIR / f"{safe_code}_{timestamp}.jpg"


def attendance_snapshot_path(employee_id: int | None, unknown: bool = False) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if unknown:
        return UNKNOWN_DIR / f"unknown_{timestamp}.jpg"
    prefix = str(employee_id) if employee_id is not None else "event"
    return LOGS_DIR / f"{prefix}_{timestamp}.jpg"


def bgr_to_rgb_image(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def open_camera(camera_index: int = 0) -> cv2.VideoCapture | None:
    """Open camera for face capture.

    Args:
        camera_index: Camera device index (default 0)

    Returns:
        OpenCV VideoCapture object or None if failed
    """
    try:
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            # Set camera properties for better performance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        else:
            cap.release()
            return None
    except Exception:
        return None