"""Automatic continuous face recognition and attendance logging."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import cv2
import numpy as np

import database as db
import face_utils as fu
import models


class AutoAttendanceEngine:
    """Runs continuous face recognition and logs attendance automatically."""

    def __init__(self, callback: Callable[[dict[str, Any]], None]):
        """Initialize the auto-attendance engine.
        
        Args:
            callback: Function to call with recognition results
        """
        self.callback = callback
        self.running = False
        self.thread: threading.Thread | None = None
        self.cap: cv2.VideoCapture | None = None
        self.known_encodings: list[np.ndarray] = []
        self.known_meta: list[dict[str, Any]] = []
        self.last_logged_employees: dict[int, datetime] = {}
        self.anti_duplicate_seconds = models.ANTI_DUPLICATE_SECONDS

    def start(self) -> bool:
        """Start continuous background scanning."""
        if self.running:
            return False

        if not fu.face_engine_available():
            self.callback({"status": "error", "message": fu.get_engine_error()})
            return False

        # Load known faces
        self.known_encodings, self.known_meta = models.load_known_faces()
        if not self.known_encodings:
            self.callback({"status": "error", "message": "Ҳанӯз ягон корманд сабт нашудааст."})
            return False

        # Open camera
        self.cap = fu.open_camera()
        if self.cap is None or not self.cap.isOpened():
            self.callback({"status": "error", "message": "❌ Камера кушода нашуд."})
            return False

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.callback({"status": "started", "message": "✅ Auto-attendance STARTED"})
        return True

    def stop(self) -> None:
        """Stop continuous scanning."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        if self.cap:
            self.cap.release()
            self.cap = None
        self.callback({"status": "stopped", "message": "⏸ Auto-attendance STOPPED"})

    def _run_loop(self) -> None:
        """Main recognition loop (runs in background thread)."""
        analysis_tick = 0
        frame_skip = 4  # Process every 4th frame for performance

        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    break

                ok, frame = self.cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue

                analysis_tick += 1

                # Process face recognition every N frames
                if analysis_tick % frame_skip == 0:
                    try:
                        faces = fu.extract_faces(frame)
                        if len(faces) == 1:
                            self._process_single_face(frame, faces[0])
                        elif len(faces) == 0:
                            self.callback({"status": "scanning", "message": "👀 No face detected..."})
                        else:
                            self.callback({
                                "status": "scanning",
                                "message": f"⚠ {len(faces)} faces detected (need 1)",
                            })
                    except Exception as exc:
                        self.callback({"status": "error", "message": f"Face detection error: {exc}"})

                time.sleep(0.03)  # ~30ms = ~33 FPS

            except Exception as exc:
                self.callback({"status": "error", "message": f"Loop error: {exc}"})
                break

    def _process_single_face(self, frame: np.ndarray, face: dict[str, Any]) -> None:
        """Process a single detected face."""
        match = fu.compare_face(face["encoding"], self.known_encodings, self.known_meta)
        event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if match["recognized"]:
            employee_id = match["employee_id"]
            full_name = match["full_name"]

            # Check anti-duplicate protection
            last_time = self.last_logged_employees.get(employee_id)
            if last_time and (datetime.now() - last_time) < timedelta(seconds=self.anti_duplicate_seconds):
                # Too soon - skip logging
                secs_left = self.anti_duplicate_seconds - int((datetime.now() - last_time).total_seconds())
                self.callback({
                    "status": "scanning",
                    "message": f"⚠ {full_name} (wait {secs_left}s)",
                    "full_name": full_name,
                    "confidence": match["confidence"],
                })
                return

            # Log the attendance
            snapshot_path = fu.save_frame(frame, fu.log_snapshot_path(employee_id=employee_id))
            db.save_log(
                employee_id=employee_id,
                full_name=full_name,
                event_type="IN",
                event_time=event_time,
                confidence=match["confidence"],
                image_path=snapshot_path,
            )

            self.last_logged_employees[employee_id] = datetime.now()
            self.callback({
                "status": "recognized",
                "message": f"✅ {full_name}",
                "full_name": full_name,
                "event_time": event_time,
                "confidence": match["confidence"],
                "snapshot_path": snapshot_path,
            })

        else:
            # Unknown person - log it
            snapshot_path = fu.save_frame(frame, fu.log_snapshot_path(unknown=True))
            db.save_log(
                employee_id=None,
                full_name="Unknown Person",
                event_type="IN",
                event_time=event_time,
                confidence=match["confidence"],
                image_path=snapshot_path,
            )

            self.callback({
                "status": "unknown",
                "message": f"🚫 Unknown ({match['confidence']:.0%})",
                "full_name": "Unknown Person",
                "event_time": event_time,
                "confidence": match["confidence"],
                "snapshot_path": snapshot_path,
            })
