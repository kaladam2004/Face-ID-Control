"""
tests/seed_data.py - Маълумоти намунавӣ барои тест
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import DatabaseManager
from core.employees import EmployeeManager
from core.attendance import AttendanceProcessor
from core.event_parser import DahuaEvent
from config import settings
from utils.logger import setup_logging
from datetime import datetime, date, timedelta
import random

setup_logging()
logger = logging.getLogger(__name__)

SAMPLE_EMPLOYEES = [
    {"employee_id": "EMP001", "dahua_user_id": "1", "full_name": "Алиев Алӣ Алиевич",     "position": "Омӯзгори математика", "phone": "+992901000001"},
    {"employee_id": "EMP002", "dahua_user_id": "2", "full_name": "Раҳимова Малика Ҷӯраевна","position": "Омӯзгори тоҷикӣ",    "phone": "+992901000002"},
    {"employee_id": "EMP003", "dahua_user_id": "3", "full_name": "Назаров Бобур Назарович", "position": "Омӯзгори физика",     "phone": "+992901000003"},
    {"employee_id": "EMP004", "dahua_user_id": "4", "full_name": "Юсупова Зарина Ҳасановна","position": "Мудири таҳсилот",     "phone": "+992901000004"},
    {"employee_id": "EMP005", "dahua_user_id": "5", "full_name": "Каримов Дилшод Каримович","position": "Омӯзгори химия",      "phone": "+992901000005"},
    {"employee_id": "EMP006", "dahua_user_id": "6", "full_name": "Мирзоева Гулноз Мирзоевна","position": "Котиб",              "phone": "+992901000006"},
    {"employee_id": "EMP007", "dahua_user_id": "7", "full_name": "Саидов Умед Саидович",   "position": "Муҳофиз",             "phone": "+992901000007"},
]

# Корманди 7 - шанбе ҳам кор мекунад
SCHEDULES = {
    "EMP007": {"work_start_time": "07:00", "work_end_time": "19:00", "work_days": "Mon,Tue,Wed,Thu,Fri,Sat"},
}


def seed(db: DatabaseManager, emp_mgr: EmployeeManager, att_proc: AttendanceProcessor):
    logger.info("=== Seeding sample data ===")

    # Кормандон
    for emp in SAMPLE_EMPLOYEES:
        emp_mgr.add_employee(**emp)
        sched = SCHEDULES.get(emp["employee_id"], {})
        emp_mgr.set_schedule(
            emp["employee_id"],
            work_start_time=sched.get("work_start_time", "08:00"),
            work_end_time=sched.get("work_end_time", "16:00"),
            work_days=sched.get("work_days", "Mon,Tue,Wed,Thu,Fri"),
        )
        logger.info(f"  Added: {emp['full_name']}")

    # 5 рӯзи охирро simulate кун
    today = date.today()
    for days_back in range(4, -1, -1):
        sim_date = today - timedelta(days=days_back)
        if sim_date.weekday() >= 5:
            continue  # Якшанбе/Шанбе (ба ғайр аз EMP007)

        logger.info(f"  Simulating {sim_date}...")

        for emp in SAMPLE_EMPLOYEES:
            emp_id = emp["employee_id"]
            dahua_id = emp["dahua_user_id"]

            # EMP007 шанбе ҳам кор мекунад
            work_days = SCHEDULES.get(emp_id, {}).get("work_days", "Mon,Tue,Wed,Thu,Fri")
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            if day_names[sim_date.weekday()] not in work_days:
                continue

            # Баъзеҳо ғоиб — 10% эҳтимол
            if random.random() < 0.10:
                att_proc.db.execute(
                    """INSERT OR IGNORE INTO daily_attendance
                       (employee_id, attendance_date, status, work_start_time, work_end_time)
                       VALUES (?,?,'absent','08:00','16:00')""",
                    (emp_id, sim_date.strftime("%Y-%m-%d")),
                )
                continue

            # Вақти омадан: 07:45 — 08:30 (баъзеҳо дер)
            late_mins = random.choices([0, 0, 0, random.randint(5, 30)], weights=[70, 10, 10, 10])[0]
            in_hour = 8
            in_min = late_mins

            # Вақти рафтан: 15:30 — 16:30 (баъзеҳо барвақт)
            early_mins = random.choices([0, 0, random.randint(5, 25)], weights=[70, 20, 10])[0]
            out_hour = 16
            out_min = -early_mins

            in_dt = datetime(sim_date.year, sim_date.month, sim_date.day, in_hour, in_min % 60, random.randint(0, 59))
            out_dt = datetime(sim_date.year, sim_date.month, sim_date.day, out_hour + (out_min // 60), abs(out_min % 60), random.randint(0, 59))

            # IN event
            ev_in = DahuaEvent()
            ev_in.code = "_DoorFace_"
            ev_in.user_id = dahua_id
            ev_in.event_time = in_dt
            ev_in.similarity = round(random.uniform(85.0, 99.9), 1)
            ev_in.alive = 1
            att_proc.process_event(ev_in, "IN")

            # OUT event
            ev_out = DahuaEvent()
            ev_out.code = "_DoorFace_"
            ev_out.user_id = dahua_id
            ev_out.event_time = out_dt
            ev_out.similarity = round(random.uniform(85.0, 99.9), 1)
            ev_out.alive = 1
            att_proc.process_event(ev_out, "OUT")

    logger.info("=== Seeding complete! ===")


def main():
    settings.ensure_dirs()
    db = DatabaseManager(settings.DATABASE_PATH)
    emp_mgr = EmployeeManager(db)
    att_proc = AttendanceProcessor(db, emp_mgr)
    seed(db, emp_mgr, att_proc)
    print("\n✅ Test data seeded successfully!")
    print(f"   Database: {settings.DATABASE_PATH}")


if __name__ == "__main__":
    main()
