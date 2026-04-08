"""Configuration management using .env file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use environment variables directly

BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DB_PATH = Path(os.getenv("DB_PATH", "data/attendance.db")).resolve()

# Cameras
CAMERA_URLS = []
for i in range(1, 10):  # Support up to 9 cameras
    url = os.getenv(f"CAMERA_{i}_URL")
    if url:
        CAMERA_URLS.append(url)

# Performance
FRAME_SKIP = int(os.getenv("FRAME_SKIP", "2"))
RESIZE_WIDTH = int(os.getenv("RESIZE_WIDTH", "640"))
RESIZE_HEIGHT = int(os.getenv("RESIZE_HEIGHT", "480"))

# Recognition
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.50"))
DUPLICATE_TIMEOUT = int(os.getenv("DUPLICATE_TIMEOUT", "30"))

# Access Control Times
WORK_HOURS_START = os.getenv("WORK_HOURS_START", "08:00")
WORK_HOURS_END = os.getenv("WORK_HOURS_END", "18:00")
SCHOOL_HOURS_START = os.getenv("SCHOOL_HOURS_START", "07:00")
SCHOOL_HOURS_END = os.getenv("SCHOOL_HOURS_END", "16:00")

# Turnstile
TURNSTILE_MODE = os.getenv("TURNSTILE_MODE", "SIMULATE")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Directories
PHOTOS_DIR = BASE_DIR / "photos"
LOGS_DIR = BASE_DIR / "logs"
UNKNOWN_DIR = LOGS_DIR / "unknown"
DATA_DIR = BASE_DIR / "data"

# Ensure directories exist
for dir_path in [PHOTOS_DIR, LOGS_DIR, UNKNOWN_DIR, DATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)