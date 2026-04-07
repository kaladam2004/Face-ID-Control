"""SQLite database layer for the Attendance / Mini-Turnstile app."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "attendance.db"
PHOTOS_DIR = BASE_DIR / "photos"
LOGS_DIR = BASE_DIR / "logs"
UNKNOWN_DIR = LOGS_DIR / "unknown"


def init_db() -> None:
    """Create folders and database tables if they do not exist."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    UNKNOWN_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name     TEXT NOT NULL,
                employee_code TEXT NOT NULL UNIQUE,
                photo_path    TEXT,
                face_encoding TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                full_name   TEXT NOT NULL,
                event_type  TEXT NOT NULL DEFAULT 'IN',
                event_time  TEXT NOT NULL,
                confidence  REAL,
                image_path  TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_employee_time ON logs(employee_id, event_time DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_employees_code ON employees(employee_code)"
        )
        conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_employee(
    full_name: str,
    employee_code: str,
    photo_path: str,
    face_encoding: str,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO employees (full_name, employee_code, photo_path, face_encoding)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, employee_code, photo_path, face_encoding),
        )
        conn.commit()
        return int(cursor.lastrowid)


def employee_code_exists(employee_code: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM employees WHERE employee_code = ?",
            (employee_code,),
        ).fetchone()
    return row is not None


def get_all_employees() -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM employees WHERE face_encoding IS NOT NULL ORDER BY id ASC"
        ).fetchall()
    return list(rows)


def save_log(
    employee_id: int | None,
    full_name: str,
    event_type: str,
    confidence: float | None,
    image_path: str | None,
    event_time: str | None = None,
) -> int:
    event_time = event_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO logs (employee_id, full_name, event_type, event_time, confidence, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (employee_id, full_name, event_type, event_time, confidence, image_path),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_recent_logs(limit: int = 100) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, employee_id, full_name, event_type, event_time, confidence, image_path
            FROM logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return list(rows)


def get_last_log_time(employee_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT event_time
            FROM logs
            WHERE employee_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (employee_id,),
        ).fetchone()
    return row["event_time"] if row else None


def count_employees() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM employees").fetchone()
    return int(row["total"])


def clear_all_logs() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM logs")
        conn.commit()
