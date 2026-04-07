"""Face recognition and camera helper utilities."""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    import face_recognition
except Exception:
    face_recognition = None

BASE_DIR = Path(__file__).resolve().parent
PHOTOS_DIR = BASE_DIR / "photos"
LOGS_DIR = BASE_DIR / "logs"
UNKNOWN_DIR = LOGS_DIR / "unknown"

CONFIDENCE_THRESHOLD = 0.50
FRAME_WIDTH = 960
FRAME_HEIGHT = 540


def face_engine_available() -> bool:
    return face_recognition is not None


def get_engine_error() -> str:
    return (
        "Модули face_recognition / dlib дастрас нестанд. "
        "Барои macOS M1/M2 ва Windows аввал requirements-ро насб кунед."
    )


def ensure_directories() -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    UNKNOWN_DIR.mkdir(parents=True, exist_ok=True)


def encoding_to_str(encoding: np.ndarray) -> str:
    return json.dumps(encoding.tolist())


def str_to_encoding(encoding_str: str) -> np.ndarray:
    return np.asarray(json.loads(encoding_str), dtype=np.float64)


def _camera_candidates() -> list[tuple[int, int | None]]:
    system = platform.system()
    candidates: list[tuple[int, int | None]] = []

    if system == "Darwin":
        candidates.extend([
            (0, cv2.CAP_AVFOUNDATION),
            (1, cv2.CAP_AVFOUNDATION),
            (0, cv2.CAP_ANY),
            (1, cv2.CAP_ANY),
        ])
    elif system == "Windows":
        candidates.extend([
            (0, cv2.CAP_DSHOW),
            (0, cv2.CAP_MSMF),
            (1, cv2.CAP_DSHOW),
            (1, cv2.CAP_MSMF),
            (0, cv2.CAP_ANY),
        ])
    else:
        candidates.extend([
            (0, cv2.CAP_ANY),
            (1, cv2.CAP_ANY),
        ])

    return candidates


def open_camera() -> cv2.VideoCapture | None:
    ensure_directories()
    for index, backend in _camera_candidates():
        cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
        if not cap or not cap.isOpened():
            if cap:
                cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok, _ = cap.read()
        if ok:
            return cap
        cap.release()
    return None


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
) -> dict[str, Any]:
    if not known_encodings:
        return {
            "recognized": False,
            "employee_id": None,
            "full_name": "Unknown Person",
            "confidence": 0.0,
            "distance": 1.0,
        }

    distances = face_recognition.face_distance(known_encodings, face_encoding)
    best_idx = int(np.argmin(distances))
    best_distance = float(distances[best_idx])
    confidence = max(0.0, min(1.0, 1.0 - best_distance))
    best_person = known_meta[best_idx]

    if confidence >= CONFIDENCE_THRESHOLD:
        return {
            "recognized": True,
            "employee_id": best_person["employee_id"],
            "full_name": best_person["full_name"],
            "confidence": confidence,
            "distance": best_distance,
        }

    return {
        "recognized": False,
        "employee_id": None,
        "full_name": "Unknown Person",
        "confidence": confidence,
        "distance": best_distance,
    }


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
        color = (52, 152, 219)

        if known_encodings and known_meta:
            match = compare_face(face["encoding"], known_encodings, known_meta)
            if match["recognized"]:
                label = f"{match['full_name']} ({match['confidence']:.0%})"
                color = (34, 197, 94)
            else:
                label = f"Unknown ({match['confidence']:.0%})"
                color = (239, 68, 68)
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


def log_snapshot_path(employee_id: int | None = None, unknown: bool = False) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if unknown:
        return UNKNOWN_DIR / f"unknown_{timestamp}.jpg"
    prefix = str(employee_id) if employee_id is not None else "event"
    return LOGS_DIR / f"{prefix}_{timestamp}.jpg"


def bgr_to_rgb_image(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
