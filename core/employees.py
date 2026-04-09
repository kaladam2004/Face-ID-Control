"""
core/employees.py - Идоракунии кормандон
"""
import logging
from typing import Optional, List, Dict
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class EmployeeManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def add_employee(
        self,
        employee_id: str,
        full_name: str,
        dahua_user_id: str = None,
        position: str = None,
        phone: str = None,
        status: str = "active",
    ) -> int:
        rowid = self.db.execute(
            """INSERT OR REPLACE INTO employees
               (employee_id, dahua_user_id, full_name, position, phone, status, updated_at)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (employee_id, dahua_user_id, full_name, position, phone, status),
        )
        logger.info(f"Employee added/updated: {employee_id} - {full_name}")
        return rowid

    def get_by_dahua_id(self, dahua_user_id: str) -> Optional[Dict]:
        return self.db.fetchone(
            "SELECT * FROM employees WHERE dahua_user_id=? AND status='active'",
            (dahua_user_id,),
        )

    def get_by_employee_id(self, employee_id: str) -> Optional[Dict]:
        return self.db.fetchone(
            "SELECT * FROM employees WHERE employee_id=?", (employee_id,)
        )

    def get_all_active(self) -> List[Dict]:
        return self.db.fetchall(
            "SELECT * FROM employees WHERE status='active' ORDER BY full_name"
        )

    def get_all(self) -> List[Dict]:
        return self.db.fetchall("SELECT * FROM employees ORDER BY full_name")

    def deactivate(self, employee_id: str):
        self.db.execute(
            "UPDATE employees SET status='inactive', updated_at=datetime('now') WHERE employee_id=?",
            (employee_id,),
        )

    def set_schedule(
        self,
        employee_id: str,
        work_start_time: str = "08:00",
        work_end_time: str = "16:00",
        work_days: str = "Mon,Tue,Wed,Thu,Fri",
        schedule_name: str = "default",
    ):
        # Кӯҳнаи schedule-ро ғайрифаъол кунед
        self.db.execute(
            """INSERT OR REPLACE INTO schedules
               (employee_id, schedule_name, work_start_time, work_end_time, work_days, is_default)
               VALUES (?,?,?,?,?,1)""",
            (employee_id, schedule_name, work_start_time, work_end_time, work_days),
        )
        logger.info(f"Schedule set for {employee_id}: {work_start_time}-{work_end_time} ({work_days})")

    def get_schedule(self, employee_id: str) -> Optional[Dict]:
        """Ҷадвали корӣ барои корманд"""
        sched = self.db.fetchone(
            """SELECT * FROM schedules WHERE employee_id=? AND is_default=1
               ORDER BY id DESC LIMIT 1""",
            (employee_id,),
        )
        if not sched:
            # Агар schedule нашуд, системавии пешфарзро баргардон
            from config import settings
            return {
                "work_start_time": settings.WORK_START_TIME,
                "work_end_time": settings.WORK_END_TIME,
                "work_days": settings.WORK_DAYS_STR,
            }
        return sched
