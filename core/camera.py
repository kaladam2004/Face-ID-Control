"""Camera management for live video feeds."""

from __future__ import annotations

import platform
from typing import Any

import cv2

from core.config import CAMERA_URLS, FRAME_SKIP, RESIZE_WIDTH, RESIZE_HEIGHT


class CameraManager:
    """Manages multiple camera feeds (USB and RTSP)."""

    def __init__(self):
        self.cameras: dict[str, cv2.VideoCapture] = {}
        self.camera_info: dict[str, dict[str, Any]] = {}
        self.frame_counters: dict[str, int] = {}

    def initialize_cameras(self) -> dict[str, bool]:
        """Initialize all configured cameras.

        Returns:
            Dict of camera_id -> success status
        """
        results = {}

        for i, url in enumerate(CAMERA_URLS, 1):
            camera_id = f"cam_{i}"
            success = self._open_camera(camera_id, url)
            results[camera_id] = success
            self.frame_counters[camera_id] = 0

        return results

    def _open_camera(self, camera_id: str, url: str) -> bool:
        """Open a single camera."""
        try:
            # Determine backend based on URL
            if url.isdigit():
                # USB camera index
                index = int(url)
                backend = self._get_usb_backend()
                cap = cv2.VideoCapture(index, backend)
            else:
                # RTSP URL
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

            if not cap or not cap.isOpened():
                print(f"Failed to open camera {camera_id}: {url}")
                return False

            # Configure camera
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, RESIZE_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESIZE_HEIGHT)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Test read
            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"Failed to read from camera {camera_id}")
                cap.release()
                return False

            self.cameras[camera_id] = cap
            self.camera_info[camera_id] = {
                "url": url,
                "ip": self._extract_ip(url),
                "type": "usb" if url.isdigit() else "rtsp"
            }

            print(f"Camera {camera_id} opened successfully: {url}")
            return True

        except Exception as e:
            print(f"Error opening camera {camera_id}: {e}")
            return False

    def _get_usb_backend(self) -> int:
        """Get appropriate backend for USB cameras."""
        system = platform.system()
        if system == "Darwin":
            return cv2.CAP_AVFOUNDATION
        elif system == "Windows":
            return cv2.CAP_DSHOW
        else:
            return cv2.CAP_V4L2

    def _extract_ip(self, url: str) -> str | None:
        """Extract IP address from RTSP URL."""
        if "@" in url and "://" in url:
            # rtsp://user:pass@192.168.1.100:554/...
            parts = url.split("@")
            if len(parts) > 1:
                ip_part = parts[1].split(":")[0]
                return ip_part
        return None

    def get_frame(self, camera_id: str, skip_frames: bool = True) -> tuple[bool, Any, str]:
        """Get next frame from camera.

        Returns:
            (success, frame, camera_ip)
        """
        if camera_id not in self.cameras:
            return False, None, None

        cap = self.cameras[camera_id]

        if skip_frames:
            self.frame_counters[camera_id] += 1
            if self.frame_counters[camera_id] % FRAME_SKIP != 0:
                return False, None, self.camera_info[camera_id]["ip"]

        ret, frame = cap.read()
        if not ret:
            return False, None, self.camera_info[camera_id]["ip"]

        # Resize for performance
        if frame.shape[1] != RESIZE_WIDTH or frame.shape[0] != RESIZE_HEIGHT:
            frame = cv2.resize(frame, (RESIZE_WIDTH, RESIZE_HEIGHT))

        return True, frame, self.camera_info[camera_id]["ip"]

    def get_all_camera_ids(self) -> list[str]:
        """Get list of active camera IDs."""
        return list(self.cameras.keys())

    def release_all(self) -> None:
        """Release all camera resources."""
        for cap in self.cameras.values():
            cap.release()
        self.cameras.clear()
        self.camera_info.clear()
        self.frame_counters.clear()