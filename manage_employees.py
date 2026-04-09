"""
manage_employees.py - CLI барои идоракунии кормандон
Истифода:
    python manage_employees.py list
    python manage_employees.py add
    python manage_employees.py set-schedule EMP001
    python manage_employees.py report today
    python manage_employees.py report weekly
    python manage_employees.py report monthly
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import settings
from core.database import DatabaseManager
from core.employees import EmployeeManager
from core.attendance import AttendanceProcessor
from reports.excel_report import (
    generate_daily_report, generate_period_report,
    get_weekly_dates, get_monthly_dates,
)
from datetime import date
from utils.logger import setup_logging

setup_logging("WARNING")


def get_components():
    settings.ensure_dirs()
    db = DatabaseManager(settings.DATABASE_PATH)
    emp_mgr = EmployeeManager(db)
    att_proc = AttendanceProcessor(db, emp_mgr)
    return db, emp_mgr, att_proc


def cmd_list(args):
    _, emp_mgr, _ = get_components()
    employees = emp_mgr.get_all()
    if not employees:
        print("Ҳеҷ корманде нест.")
        return

    print(f"\n{'ID':<8} {'Dahua ID':<10} {'Ному насаб':<30} {'Вазифа':<25} {'Статус'}")
    print("-" * 90)
    for e in employees:
        print(
            f"{e['employee_id']:<8} {e['dahua_user_id'] or '—':<10} "
            f"{e['full_name']:<30} {(e['position'] or '—'):<25} {e['status']}"
        )
    print(f"\nЯкумла: {len(employees)} корманд")


def cmd_add(args):
    _, emp_mgr, _ = get_components()
    print("\n=== Иловакунии корманди нав ===")
    emp_id = input("Employee ID (мисол: EMP010): ").strip()
    dahua_id = input("Dahua UserID: ").strip()
    name = input("Ному насаб: ").strip()
    position = input("Вазифа: ").strip()
    phone = input("Телефон (ихтиёрӣ): ").strip()

    emp_mgr.add_employee(
        employee_id=emp_id,
        full_name=name,
        dahua_user_id=dahua_id or None,
        position=position or None,
        phone=phone or None,
    )

    print("\nЖадвали корӣ:")
    start = input(f"Вақти оғоз [{settings.WORK_START_TIME}]: ").strip() or settings.WORK_START_TIME
    end = input(f"Вақти анҷом [{settings.WORK_END_TIME}]: ").strip() or settings.WORK_END_TIME
    days = input(f"Рӯзҳои корӣ [{settings.WORK_DAYS_STR}]: ").strip() or settings.WORK_DAYS_STR
    emp_mgr.set_schedule(emp_id, start, end, days)

    print(f"\n✅ Корманд иловашуд: {name} (ID: {emp_id})")


def cmd_set_schedule(args):
    _, emp_mgr, _ = get_components()
    emp_id = args.employee_id
    emp = emp_mgr.get_by_employee_id(emp_id)
    if not emp:
        print(f"❌ Корманд {emp_id} нашуд.")
        return

    print(f"\nЖадвали корӣ барои: {emp['full_name']}")
    sched = emp_mgr.get_schedule(emp_id)
    start = input(f"Вақти оғоз [{sched['work_start_time']}]: ").strip() or sched["work_start_time"]
    end = input(f"Вақти анҷом [{sched['work_end_time']}]: ").strip() or sched["work_end_time"]
    days = input(f"Рӯзҳои корӣ [{sched['work_days']}]: ").strip() or sched["work_days"]
    emp_mgr.set_schedule(emp_id, start, end, days)
    print(f"✅ Жадвал навсозишуд: {start}–{end} ({days})")


def cmd_report(args):
    _, emp_mgr, att_proc = get_components()
    rtype = args.type

    if rtype == "today":
        today = date.today()
        records = att_proc.get_daily_report(today)
        fp = generate_daily_report(records, today)
        print(f"✅ Ҳисоботи рӯзона: {fp}")

    elif rtype == "weekly":
        start, end = get_weekly_dates()
        records = att_proc.get_period_report(start, end)
        fp = generate_period_report(records, start, end, "weekly")
        print(f"✅ Ҳисоботи ҳафтаина: {fp}")

    elif rtype == "monthly":
        start, end = get_monthly_dates()
        records = att_proc.get_period_report(start, end)
        fp = generate_period_report(records, start, end, "monthly")
        print(f"✅ Ҳисоботи моҳона: {fp}")

    elif rtype == "custom":
        start_str = input("Аз санаи (YYYY-MM-DD): ").strip()
        end_str = input("То санаи (YYYY-MM-DD): ").strip()
        from datetime import datetime
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
        records = att_proc.get_period_report(start, end)
        fp = generate_period_report(records, start, end, "custom")
        print(f"✅ Ҳисобот: {fp}")


def main():
    parser = argparse.ArgumentParser(description="Dahua Attendance — Employee Manager")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="Рӯйхати кормандон")
    sub.add_parser("add", help="Иловакунии корманд")

    sched_p = sub.add_parser("set-schedule", help="Танзими жадвали корӣ")
    sched_p.add_argument("employee_id", help="Employee ID")

    rep_p = sub.add_parser("report", help="Барориши ҳисобот")
    rep_p.add_argument(
        "type",
        choices=["today", "weekly", "monthly", "custom"],
        help="Навъи ҳисобот",
    )

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "set-schedule":
        cmd_set_schedule(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
