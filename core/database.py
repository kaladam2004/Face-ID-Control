"""
core/database.py - Идоракунии база ва schema
"""
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- ================================================================
-- EMPLOYEES - Кормандон
-- ================================================================
CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     TEXT UNIQUE NOT NULL,
    dahua_user_id   TEXT UNIQUE,
    full_name       TEXT NOT NULL,
    position        TEXT,
    phone           TEXT,
    status          TEXT DEFAULT 'active' CHECK(status IN ('active','inactive')),
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ================================================================
-- SCHEDULES - Ҷадвали корӣ
-- ================================================================
CREATE TABLE IF NOT EXISTS schedules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     TEXT NOT NULL,
    schedule_name   TEXT DEFAULT 'default',
    work_start_time TEXT NOT NULL DEFAULT '08:00',
    work_end_time   TEXT NOT NULL DEFAULT '16:00',
    work_days       TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri',
    is_default      INTEGER DEFAULT 0,
    effective_from  TEXT,
    effective_to    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- ================================================================
-- RAW_EVENTS - Ҳамаи event-ҳои хоми Dahua
-- ================================================================
CREATE TABLE IF NOT EXISTS raw_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_ip       TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK(direction IN ('IN','OUT')),
    dahua_user_id   TEXT,
    event_code      TEXT,
    event_data      TEXT,
    event_time      TEXT,
    similarity      REAL,
    alive           INTEGER,
    real_utc        TEXT,
    door            TEXT,
    open_method     TEXT,
    is_processed    INTEGER DEFAULT 0,
    received_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_events_user_time
    ON raw_events(dahua_user_id, event_time);
CREATE INDEX IF NOT EXISTS idx_raw_events_processed
    ON raw_events(is_processed);

-- ================================================================
-- DAILY_ATTENDANCE - Ҳозиршавии рӯзона
-- ================================================================
CREATE TABLE IF NOT EXISTS daily_attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     TEXT NOT NULL,
    attendance_date TEXT NOT NULL,
    first_in        TEXT,
    last_out        TEXT,
    late_minutes    INTEGER DEFAULT 0,
    early_leave_min INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'absent'
                    CHECK(status IN ('present','absent','late','early_leave','late_and_early')),
    work_start_time TEXT,
    work_end_time   TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(employee_id, attendance_date),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_attendance_date
    ON daily_attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_daily_attendance_employee
    ON daily_attendance(employee_id);

-- ================================================================
-- NOTIFICATIONS_LOG - Логи огоҳиҳо
-- ================================================================
CREATE TABLE IF NOT EXISTS notifications_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_type TEXT,
    chat_id         TEXT,
    message_preview TEXT,
    status          TEXT DEFAULT 'sent',
    sent_at         TEXT DEFAULT (datetime('now'))
);

-- ================================================================
-- SYSTEM_SETTINGS - Танзимоти система
-- ================================================================
CREATE TABLE IF NOT EXISTS system_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    description     TEXT,
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Default settings
INSERT OR IGNORE INTO system_settings (key, value, description) VALUES
    ('duplicate_timeout_minutes', '2', 'Вақти duplicate барои чашмдошт (дақиқа)'),
    ('work_start_time', '08:00', 'Вақти оғози корӣ'),
    ('work_end_time', '16:00', 'Вақти анҷоми корӣ'),
    ('work_days', 'Mon,Tue,Wed,Thu,Fri', 'Рӯзҳои корӣ'),
    ('timezone', 'Asia/Dushanbe', 'Минтақаи вақт'),
    ('notify_morning', '09:00', 'Вақти огоҳии субҳ'),
    ('notify_late_check', '08:15', 'Вақти санҷиши дермонӣ'),
    ('notify_evening', '17:00', 'Вақти огоҳии бегоҳ');
"""


class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params=()) -> Optional[int]:
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid

    def fetchone(self, sql: str, params=()) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params=()) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_setting(self, key: str, default=None) -> Optional[str]:
        row = self.fetchone("SELECT value FROM system_settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self.execute(
            "INSERT OR REPLACE INTO system_settings(key,value,updated_at) VALUES(?,?,datetime('now'))",
            (key, value)
        )
