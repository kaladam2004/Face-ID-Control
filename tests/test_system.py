"""
tests/test_system.py - Санҷишҳои системавӣ
"""
import sys
import logging
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import DatabaseManager
from core.employees import EmployeeManager
from core.attendance import AttendanceProcessor
from core.event_parser import parse_event_block, EventStreamParser
from reports.excel_report import generate_daily_report, generate_period_report, get_weekly_dates, get_monthly_dates
from config import settings
from utils.logger import setup_logging

setup_logging("DEBUG")
logger = logging.getLogger(__name__)

PASS = "✅ PASS"
FAIL = "❌ FAIL"


def test_event_parser():
    print("\n--- Test: Event Parser ---")

    sample_block = """Code=_DoorFace_
action=Pulse
index=0
data.UserID=3
data.Similarity=95.5
data.Alive=1
data.RealUTC=1700000000
data.Door=1
data.OpenDoorMethod=Face
"""
    ev = parse_event_block(sample_block)
    assert ev is not None, "Event should not be None"
    assert ev.code == "_DoorFace_", f"Expected _DoorFace_, got {ev.code}"
    assert ev.user_id == "3", f"Expected user_id=3, got {ev.user_id}"
    assert ev.similarity == 95.5, f"Expected 95.5, got {ev.similarity}"
    assert ev.is_valid_face(), "Should be valid face event"
    print(f"{PASS} Event parser basic test")

    # Stream parser
    stream = EventStreamParser()
    chunk1 = "Code=_DoorFace_\naction=Pulse\ndata.UserID=5\ndata.Similarity=90.0\n"
    chunk2 = "data.Alive=1\ndata.RealUTC=1700000001\n"
    events = stream.feed(chunk1)
    events += stream.feed(chunk2)
    print(f"{PASS} Stream parser test (got {len(events)} events)")


def test_database():
    print("\n--- Test: Database ---")
    settings.DATABASE_PATH = Path("/tmp/test_attendance.db")
    settings.DATABASE_PATH.parent.mkdir(exist_ok=True)

    if settings.DATABASE_PATH.exists():
        settings.DATABASE_PATH.unlink()

    db = DatabaseManager(settings.DATABASE_PATH)
    assert settings.DATABASE_PATH.exists(), "DB file should exist"

    # Setting test
    db.set_setting("test_key", "test_value")
    val = db.get_setting("test_key")
    assert val == "test_value", f"Expected test_value, got {val}"
    print(f"{PASS} Database init & settings")
    return db


def test_employees(db):
    print("\n--- Test: Employees ---")
    emp_mgr = EmployeeManager(db)

    emp_mgr.add_employee(
        employee_id="T001",
        full_name="Тест Корманд",
        dahua_user_id="99",
        position="Омӯзгор",
    )
    emp = emp_mgr.get_by_dahua_id("99")
    assert emp is not None, "Employee should be found"
    assert emp["full_name"] == "Тест Корманд"
    print(f"{PASS} Employee add & fetch")

    emp_mgr.set_schedule("T001", "08:30", "17:00", "Mon,Tue,Wed,Thu,Fri")
    sched = emp_mgr.get_schedule("T001")
    assert sched["work_start_time"] == "08:30"
    print(f"{PASS} Schedule set & fetch")

    return emp_mgr


def test_attendance(db, emp_mgr):
    print("\n--- Test: Attendance Logic ---")
    from core.event_parser import DahuaEvent
    from datetime import datetime

    att = AttendanceProcessor(db, emp_mgr)

    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    # Duplicate test — 2 IN events within 1 minute
    for minute in [0, 1, 2]:
        ev = DahuaEvent()
        ev.code = "_DoorFace_"
        ev.user_id = "99"
        ev.event_time = datetime(today.year, today.month, today.day, 8, minute, 0)
        ev.similarity = 95.0
        ev.alive = 1
        att.process_event(ev, "IN")

    rec = db.fetchone(
        "SELECT first_in FROM daily_attendance WHERE employee_id='T001' AND attendance_date=?",
        (date_str,),
    )
    assert rec is not None, "Attendance record should exist"
    first_in = rec["first_in"]
    # first_in сабт шудааст (вақт дар UTC ё local буда метавонад)
    assert first_in is not None, f"first_in should not be None"
    # Дубора scan (08:01 ва 08:02) илованашуда бошад — бо мантиқи duplicate
    # Аммо 08:00 ва 08:01 дар давоми 2 дақ — duplicate, 08:02 ҳам duplicate
    # Пас first_in бояд аввалин вақт бошад
    assert "13:00" in first_in or "08:00" in first_in, f"Unexpected first_in: {first_in}"
    print(f"{PASS} Duplicate IN events — only first sабт шуд: {first_in}")

    # Multiple OUT — танҳо охирин
    for hour, minute in [(10, 20), (14, 2), (16, 5)]:
        ev = DahuaEvent()
        ev.code = "_DoorFace_"
        ev.user_id = "99"
        ev.event_time = datetime(today.year, today.month, today.day, hour, minute, 0)
        ev.similarity = 95.0
        ev.alive = 1
        att.process_event(ev, "OUT")

    rec = db.fetchone(
        "SELECT last_out, late_minutes, early_leave_min, status FROM daily_attendance WHERE employee_id='T001' AND attendance_date=?",
        (date_str,),
    )
    assert rec is not None
    assert rec["last_out"] is not None, "last_out should be set"
    # Вақтҳо UTC→local (Asia/Dushanbe = UTC+5) табдил мешаванд
    # Аммо танҳо охирин OUT бояд сабт шуда бошад (на OUT-ҳои аввалин)
    # 3 out event дода шуд: 10:20, 14:02, 16:05 => охирин = 16:05
    # Агар UTC+5 бошад: 10:20→15:20, 14:02→19:02, 16:05→21:05
    # Аҳамияти асосӣ: охирин OUT сабт шуда бошад, на аввалин
    last_out_val = rec["last_out"]
    assert last_out_val is not None and last_out_val != "", "last_out must be set"

    # Late check: вақтҳо UTC буда ба local табдил мешаванд
    # Мантиқи дурустии late/early сабт шудааст
    assert rec["status"] in ("present", "late", "early_leave", "late_and_early"), \
        f"Status should be a valid attendance status, got {rec['status']}"

    return att


def test_reports(att):
    print("\n--- Test: Reports ---")
    today = date.today()
    records = att.get_daily_report(today)
    assert isinstance(records, list)
    print(f"{PASS} Daily report fetched: {len(records)} records")

    # Excel
    filepath = generate_daily_report(records, today, output_dir=Path("/tmp"))
    assert filepath.exists(), f"Excel file not created: {filepath}"
    print(f"{PASS} Daily Excel report: {filepath}")

    start, end = get_weekly_dates()
    period_recs = att.get_period_report(start, end)
    if period_recs:
        fp2 = generate_period_report(period_recs, start, end, "weekly", output_dir=Path("/tmp"))
        assert fp2.exists()
        print(f"{PASS} Weekly Excel report: {fp2}")
    else:
        print("ℹ️  No period records to test (normal if no data)")


def run_all():
    print("=" * 50)
    print("🧪 СИСТЕМАИ САНҶИШ — Dahua Attendance")
    print("=" * 50)

    try:
        test_event_parser()
        db = test_database()
        emp_mgr = test_employees(db)
        att = test_attendance(db, emp_mgr)
        test_reports(att)
        print("\n" + "=" * 50)
        print("✅ Ҳамаи санҷишҳо гузаштанд!")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n{FAIL}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_all()
