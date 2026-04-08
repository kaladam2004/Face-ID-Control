"""SQLite database layer for the Attendance / Access Control system."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from core.config import DB_PATH, PHOTOS_DIR, LOGS_DIR, UNKNOWN_DIR


def init_db() -> None:
    """Create folders and database tables if they do not exist."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    UNKNOWN_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Employees table with role and department
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT NOT NULL UNIQUE,
                full_name     TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'staff',
                department    TEXT,
                face_encoding TEXT,
                photo_path    TEXT,
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )

        # Attendance logs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id   INTEGER,
                employee_code TEXT NOT NULL,
                full_name     TEXT NOT NULL,
                role          TEXT NOT NULL,
                confidence    REAL,
                camera_ip     TEXT,
                snapshot_path TEXT,
                status        TEXT NOT NULL,  -- GRANTED, DENIED, UNKNOWN
                event_type    TEXT NOT NULL DEFAULT 'ENTRY',  -- ENTRY, EXIT
                created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
            """
        )

        # Unknown logs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS unknown_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_ip     TEXT,
                snapshot_path TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )

        # Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_logs_employee_time ON attendance_logs(employee_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_logs_status_time ON attendance_logs(status, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_employees_code ON employees(employee_code)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_employees_role ON employees(role)"
        )

        conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_employee(
    employee_code: str,
    full_name: str,
    role: str,
    department: str | None,
    photo_path: str | None,
    face_encoding: str | None,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO employees (employee_code, full_name, role, department, photo_path, face_encoding)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (employee_code, full_name, role, department, photo_path, face_encoding),
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


def get_all_employees(active_only: bool = True) -> list[sqlite3.Row]:
    query = "SELECT * FROM employees"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY id ASC"

    with get_connection() as conn:
        rows = conn.execute(query).fetchall()
    return list(rows)


def save_attendance_log(
    employee_id: int | None,
    employee_code: str,
    full_name: str,
    role: str,
    confidence: float | None,
    camera_ip: str,
    snapshot_path: str | None,
    status: str,
    event_type: str = "ENTRY",
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO attendance_logs (employee_id, employee_code, full_name, role, confidence, camera_ip, snapshot_path, status, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (employee_id, employee_code, full_name, role, confidence, camera_ip, snapshot_path, status, event_type),
        )
        conn.commit()
        return int(cursor.lastrowid)


def save_unknown_log(
    camera_ip: str,
    snapshot_path: str,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO unknown_logs (camera_ip, snapshot_path)
            VALUES (?, ?)
            """,
            (camera_ip, snapshot_path),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_recent_attendance_logs(limit: int = 100) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM attendance_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return list(rows)


def get_last_attendance_time(employee_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT created_at
            FROM attendance_logs
            WHERE employee_id = ? AND status = 'GRANTED'
            ORDER BY id DESC
            LIMIT 1
            """,
            (employee_id,),
        ).fetchone()
    return row["created_at"] if row else None


def count_employees() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM employees WHERE is_active = 1").fetchone()
    return int(row["total"])


def clear_all_logs() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM attendance_logs")
        conn.execute("DELETE FROM unknown_logs")
        conn.commit()