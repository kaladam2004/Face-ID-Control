"""Main processing engine for face recognition and access control."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from core.access_control import check_access
from core.attendance import AttendanceManager
from core.camera import CameraManager
from core.database import get_all_employees
from core.recognition import compare_face, extract_faces, str_to_encoding
from core.turnstile import deny_access, open_turnstile


class FaceRecognitionEngine:
    """Main engine for processing camera feeds and managing access control."""

    def __init__(self):
        self.camera_manager = CameraManager()
        self.attendance_manager = AttendanceManager()
        self.known_encodings: list[np.ndarray] = []
        self.known_meta: list[dict[str, Any]] = []
        self.load_known_faces()

    def load_known_faces(self) -> None:
        """Load known faces from database."""
        employees = get_all_employees()
        self.known_encodings = []
        self.known_meta = []

        for employee in employees:
            try:
                encoding = str_to_encoding(employee["face_encoding"])
                self.known_encodings.append(encoding)
                self.known_meta.append({
                    "id": employee["id"],
                    "employee_code": employee["employee_code"],
                    "full_name": employee["full_name"],
                    "role": employee["role"],
                })
            except Exception as exc:
                print(f"[WARN] Failed to load encoding for employee #{employee['id']}: {exc}")

        print(f"Loaded {len(self.known_encodings)} known faces")

    def initialize_cameras(self) -> dict[str, bool]:
        """Initialize all configured cameras."""
        return self.camera_manager.initialize_cameras()

    def process_camera_frame(self, camera_id: str) -> dict[str, Any] | None:
        """Process a single frame from the specified camera.

        Returns:
            Processing result or None if no frame available
        """
        success, frame, camera_ip = self.camera_manager.get_frame(camera_id)
        if not success or frame is None:
            return None

        try:
            faces = extract_faces(frame)
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Face detection error: {exc}",
                "camera_id": camera_id,
                "camera_ip": camera_ip,
            }

        if len(faces) == 0:
            return {
                "status": "no_face",
                "message": "No face detected",
                "camera_id": camera_id,
                "camera_ip": camera_ip,
            }

        if len(faces) > 1:
            return {
                "status": "multiple_faces",
                "message": f"Multiple faces detected ({len(faces)})",
                "camera_id": camera_id,
                "camera_ip": camera_ip,
            }

        # Process single face
        face = faces[0]
        match = compare_face(
            face["encoding"],
            self.known_encodings,
            self.known_meta,
            frame=frame,
            face_location=face["location"],
            check_liveness=True  # Enable liveness check
        )

        # Add access status to face data for annotation
        face["access_status"] = "unknown"

        if match["recognized"]:
            employee_id = match["employee_id"]
            role = match["role"]
            access_allowed = check_access(role)

            if access_allowed:
                # Log attendance and open turnstile
                log_result = self.attendance_manager.log_recognized_employee(
                    employee_id=employee_id,
                    employee_code=match["employee_code"],
                    full_name=match["full_name"],
                    role=role,
                    confidence=match["confidence"],
                    camera_ip=camera_ip,
                    frame=frame,
                    access_granted=True
                )

                if log_result["status"] == "duplicate":
                    face["access_status"] = "duplicate"
                    return {
                        "status": "duplicate",
                        "message": log_result["message"],
                        "camera_id": camera_id,
                        "camera_ip": camera_ip,
                        "full_name": match["full_name"],
                        "role": role,
                        "confidence": match["confidence"],
                    }

                # Open turnstile
                turnstile_opened = open_turnstile()
                face["access_status"] = "granted"

                return {
                    "status": "granted",
                    "message": f"ACCESS GRANTED: {match['full_name']} ({role})",
                    "camera_id": camera_id,
                    "camera_ip": camera_ip,
                    "full_name": match["full_name"],
                    "role": role,
                    "confidence": match["confidence"],
                    "log_id": log_result["log_id"],
                    "snapshot_path": log_result["snapshot_path"],
                    "turnstile_opened": turnstile_opened,
                }

            else:
                # Access denied by role/time
                log_result = self.attendance_manager.log_recognized_employee(
                    employee_id=employee_id,
                    employee_code=match["employee_code"],
                    full_name=match["full_name"],
                    role=role,
                    confidence=match["confidence"],
                    camera_ip=camera_ip,
                    frame=frame,
                    access_granted=False
                )

                deny_access()
                face["access_status"] = "denied"

                return {
                    "status": "denied",
                    "message": f"ACCESS DENIED: {match['full_name']} ({role}) - Not allowed at this time",
                    "camera_id": camera_id,
                    "camera_ip": camera_ip,
                    "full_name": match["full_name"],
                    "role": role,
                    "confidence": match["confidence"],
                    "log_id": log_result["log_id"],
                    "snapshot_path": log_result["snapshot_path"],
                }

        else:
            # Unknown face
            log_result = self.attendance_manager.log_unknown_face(camera_ip, frame)
            deny_access()
            face["access_status"] = "unknown"

            return {
                "status": "unknown",
                "message": "UNKNOWN FACE DETECTED",
                "camera_id": camera_id,
                "camera_ip": camera_ip,
                "confidence": match["confidence"],
                "log_id": log_result["log_id"],
                "snapshot_path": log_result["snapshot_path"],
            }

    def get_annotated_frame(self, camera_id: str) -> tuple[bool, Any, dict[str, Any] | None]:
        """Get frame with face annotations.

        Returns:
            (success, annotated_frame, processing_result)
        """
        success, frame, camera_ip = self.camera_manager.get_frame(camera_id, skip_frames=False)
        if not success or frame is None:
            return False, None, None

        try:
            faces = extract_faces(frame)
            annotated_frame = frame  # Default to original

            if faces:
                # Process faces for access status
                for face in faces:
                    match = compare_face(
                        face["encoding"],
                        self.known_encodings,
                        self.known_meta,
                        frame=frame,
                        face_location=face["location"],
                        check_liveness=False  # Skip for annotation
                    )

                    if match["recognized"]:
                        role = match["role"]
                        access_allowed = check_access(role)
                        face["access_status"] = "granted" if access_allowed else "denied"
                    else:
                        face["access_status"] = "unknown"

                # Import here to avoid circular import
                from core.recognition import annotate_frame
                annotated_frame = annotate_frame(frame, faces, self.known_encodings, self.known_meta)

            return True, annotated_frame, None

        except Exception as exc:
            return False, frame, {
                "status": "error",
                "message": f"Processing error: {exc}",
            }

    def shutdown(self) -> None:
        """Clean shutdown of resources."""
        self.camera_manager.release_all()