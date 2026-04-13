"""
core/attendance.py - Мантиқи асосии ҳозиршавӣ
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict
import pytz

from .database import DatabaseManager
from .employees import EmployeeManager
from config.settings import settings

logger = logging.getLogger(__name__)


def get_local_now() -> datetime:
    tz = pytz.timezone(settings.TIMEZONE)
    return datetime.now(tz)


def parse_time(time_str: str):
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except (ValueError, TypeError):
        return None


class AttendanceProcessor:
    def __init__(self, db: DatabaseManager, emp_manager: EmployeeManager):
        self.db = db
        self.emp = emp_manager
        self._last_event_cache: Dict[str, datetime] = {}
        self._ensure_guest_table()

    def _ensure_guest_table(self):
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS guest_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guest_id TEXT,
            guest_type TEXT DEFAULT 'guest_or_student',
            direction TEXT,
            event_time TEXT,
            similarity INTEGER DEFAULT 0,
            alive INTEGER DEFAULT 0,
            real_utc INTEGER DEFAULT 0,
            door INTEGER DEFAULT 0,
            open_method INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

    def process_event(self, event: dict, device_direction: str) -> bool:
        user_id = str(event.get("user_id", "")).strip()
        if not user_id:
            return False

        event_local = get_local_now()
        event_date = event_local.date()
        event_datetime_str = event_local.strftime("%Y-%m-%d %H:%M:%S")

        cache_key = f"{user_id}_{device_direction}"
        last_event = self._last_event_cache.get(cache_key)
        timeout = timedelta(minutes=settings.DUPLICATE_TIMEOUT_MINUTES)

        if last_event and (event_local - last_event) < timeout:
            logger.info(f"Duplicate ignored: user_id={user_id} ({device_direction})")
            return False

        self._last_event_cache[cache_key] = event_local

        # Ҳамеша raw event нигоҳ дор
        self.db.execute(
            """INSERT INTO raw_events
               (device_ip, direction, dahua_user_id, event_code, event_time,
                similarity, alive, real_utc, door, open_method, is_processed)
               VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
            (
                "IN_DEVICE" if device_direction == "IN" else "OUT_DEVICE",
                device_direction,
                user_id,
                "_DoorFace_",
                event_datetime_str,
                event.get("similarity", 0),
                event.get("alive", 0),
                event.get("real_utc", 0),
                event.get("door", 0),
                event.get("open_method", 0),
            ),
        )

        employee = self.emp.get_by_dahua_id(user_id)

        # =====================================================
        # 1) Агар корманд бошад
        # =====================================================
        if employee:
            self._update_daily_attendance(
                employee["employee_id"],
                event_date,
                event_datetime_str,
                device_direction,
            )

            logger.info(f"[{device_direction}] EMPLOYEE: {employee['full_name']} @ {event_datetime_str}")
            return True

        # =====================================================
        # 2) Агар корманд набошад -> меҳмон / student
        # =====================================================
        guest_type = "guest_or_student"

        self.db.execute(
            """INSERT INTO guest_events
               (guest_id, guest_type, direction, event_time,
                similarity, alive, real_utc, door, open_method)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                user_id,
                guest_type,
                device_direction,
                event_datetime_str,
                event.get("similarity", 0),
                event.get("alive", 0),
                event.get("real_utc", 0),
                event.get("door", 0),
                event.get("open_method", 0),
            ),
        )

        logger.info(f"[{device_direction}] МЕҲМОН / STUDENT: user_id={user_id} @ {event_datetime_str}")
        return True

    def _update_daily_attendance(self, employee_id: str, att_date: date, event_datetime_str: str, direction: str):
        date_str = att_date.strftime("%Y-%m-%d")

        existing = self.db.fetchone(
            "SELECT * FROM daily_attendance WHERE employee_id=? AND attendance_date=?",
            (employee_id, date_str),
        )

        if direction == "IN":
            if not existing:
                sched = self.emp.get_schedule(employee_id)
                self.db.execute(
                    """INSERT INTO daily_attendance
                       (employee_id, attendance_date, first_in, status,
                        work_start_time, work_end_time, updated_at)
                       VALUES (?,?,?,'present',?,?,datetime('now'))""",
                    (
                        employee_id,
                        date_str,
                        event_datetime_str,
                        sched["work_start_time"],
                        sched["work_end_time"],
                    ),
                )
            else:
                # Агар first_in аллакай ҳаст, дигар иваз намекунем
                pass

        elif direction == "OUT":
            if not existing:
                sched = self.emp.get_schedule(employee_id)
                self.db.execute(
                    """INSERT INTO daily_attendance
                       (employee_id, attendance_date, last_out, status,
                        work_start_time, work_end_time, updated_at)
                       VALUES (?,?,?,'present',?,?,datetime('now'))""",
                    (
                        employee_id,
                        date_str,
                        event_datetime_str,
                        sched["work_start_time"],
                        sched["work_end_time"],
                    ),
                )
            else:
                self.db.execute(
                    """UPDATE daily_attendance
                       SET last_out=?, updated_at=datetime('now')
                       WHERE employee_id=? AND attendance_date=?""",
                    (event_datetime_str, employee_id, date_str),
                )

        self._recalculate_record(employee_id, date_str)

    def _recalculate_record(self, employee_id: str, date_str: str):
        rec = self.db.fetchone(
            "SELECT * FROM daily_attendance WHERE employee_id=? AND attendance_date=?",
            (employee_id, date_str),
        )
        if not rec:
            return

        late_min = 0
        early_min = 0
        status = "present"

        work_start = parse_time(rec["work_start_time"] or settings.WORK_START_TIME)
        work_end = parse_time(rec["work_end_time"] or settings.WORK_END_TIME)
        ref_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        if rec["first_in"]:
            first_in_dt = datetime.strptime(rec["first_in"], "%Y-%m-%d %H:%M:%S")
            first_in_time = first_in_dt.time()
            if work_start and first_in_time > work_start:
                diff = datetime.combine(ref_date, first_in_time) - datetime.combine(ref_date, work_start)
                late_min = int(diff.total_seconds() / 60)

        if rec["last_out"]:
            last_out_dt = datetime.strptime(rec["last_out"], "%Y-%m-%d %H:%M:%S")
            last_out_time = last_out_dt.time()
            if work_end and last_out_time < work_end:
                diff = datetime.combine(ref_date, work_end) - datetime.combine(ref_date, last_out_time)
                early_min = int(diff.total_seconds() / 60)

        if late_min > 0 and early_min > 0:
            status = "late_and_early"
        elif late_min > 0:
            status = "late"
        elif early_min > 0:
            status = "early_leave"
        elif rec["first_in"]:
            status = "present"
        else:
            status = "absent"

        self.db.execute(
            """UPDATE daily_attendance
               SET late_minutes=?, early_leave_min=?, status=?, updated_at=datetime('now')
               WHERE employee_id=? AND attendance_date=?""",
            (late_min, early_min, status, employee_id, date_str),
        )

    # =====================================================
    # TELEGRAM / REPORT FUNCTIONS
    # =====================================================

    def get_today_present(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.fetchall("""
            SELECT e.full_name, a.first_in, a.last_out, a.status
            FROM daily_attendance a
            JOIN employees e ON e.employee_id = a.employee_id
            WHERE a.attendance_date=? AND a.first_in IS NOT NULL
            ORDER BY a.first_in ASC
        """, (today,))

    def get_today_lates(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.fetchall("""
            SELECT e.full_name, a.first_in, a.late_minutes
            FROM daily_attendance a
            JOIN employees e ON e.employee_id = a.employee_id
            WHERE a.attendance_date=? AND a.late_minutes > 0
            ORDER BY a.late_minutes DESC
        """, (today,))

    def get_today_absents(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.fetchall("""
            SELECT e.full_name
            FROM employees e
            WHERE e.status='active'
              AND e.employee_id NOT IN (
                  SELECT employee_id
                  FROM daily_attendance
                  WHERE attendance_date=? AND first_in IS NOT NULL
              )
            ORDER BY e.full_name
        """, (today,))

    def get_today_guests(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.fetchall("""
            SELECT guest_id, guest_type, direction, event_time
            FROM guest_events
            WHERE DATE(event_time)=?
            ORDER BY event_time ASC
        """, (today,))

    def get_monthly_summary(self, year: int, month: int):
        ym = f"{year:04d}-{month:02d}"
        return self.db.fetchall("""
            SELECT
                e.full_name,
                COUNT(a.id) as days_present,
                COALESCE(SUM(a.late_minutes), 0) as total_late_minutes,
                COALESCE(SUM(a.early_leave_min), 0) as total_early_leave_minutes
            FROM employees e
            LEFT JOIN daily_attendance a
              ON e.employee_id = a.employee_id
             AND substr(a.attendance_date,1,7)=?
            WHERE e.status='active'
            GROUP BY e.employee_id, e.full_name
            ORDER BY e.full_name
        """, (ym,))

    def get_daily_report(self, report_date):
        """Ҳисоботи рӯзона — ҳамаи кормандон бо статус"""
        date_str = report_date.strftime("%Y-%m-%d") if hasattr(report_date, "strftime") else report_date
        rows = self.db.fetchall("""
            SELECT
                e.employee_id,
                e.full_name,
                e.position,
                a.first_in,
                a.last_out,
                COALESCE(a.late_minutes, 0)    AS late_minutes,
                COALESCE(a.early_leave_min, 0) AS early_leave_min,
                COALESCE(a.status, 'absent')   AS status
            FROM employees e
            LEFT JOIN daily_attendance a
              ON e.employee_id = a.employee_id
             AND a.attendance_date = ?
            WHERE e.status = 'active'
            ORDER BY e.full_name
        """, (date_str,))
        return [dict(r) for r in rows]

    def get_period_report(self, start_date, end_date):
        """Ҳисоботи давра — ҳар рӯзи корӣ барои ҳар корманд"""
        start_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date
        end_str   = end_date.strftime("%Y-%m-%d")   if hasattr(end_date,   "strftime") else end_date
        rows = self.db.fetchall("""
            SELECT
                e.employee_id,
                e.full_name,
                e.position,
                a.attendance_date,
                a.first_in,
                a.last_out,
                COALESCE(a.late_minutes, 0)    AS late_minutes,
                COALESCE(a.early_leave_min, 0) AS early_leave_min,
                COALESCE(a.status, 'absent')   AS status
            FROM employees e
            LEFT JOIN daily_attendance a
              ON e.employee_id = a.employee_id
             AND a.attendance_date BETWEEN ? AND ?
            WHERE e.status = 'active'
              AND a.attendance_date IS NOT NULL
            ORDER BY e.full_name, a.attendance_date
        """, (start_str, end_str))
        return [dict(r) for r in rows]