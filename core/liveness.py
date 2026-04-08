"""Liveness detection placeholder."""

from __future__ import annotations

from typing import Any


def is_face_live(frame, face_data: dict[str, Any]) -> dict[str, Any]:
    """Placeholder for liveness detection.

    For now, always returns True. Replace with actual liveness detection logic.
    """
    return {
        "is_live": True,
        "confidence": 1.0,
        "reason": "Liveness detection not implemented - placeholder"
    }