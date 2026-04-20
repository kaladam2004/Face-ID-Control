import sys
from pathlib import Path
from datetime import date

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.database import DatabaseManager
from core.employees import EmployeeManager
from core.attendance import AttendanceProcessor
from reports.excel_report import generate_daily_report, generate_period_report, get_weekly_dates
from config import settings

def test_report_generation():
    print("Testing report generation...")
    db = DatabaseManager(settings.DATABASE_PATH)
    emp_mgr = EmployeeManager(db)
    att_proc = AttendanceProcessor(db, emp_mgr)
    
    today = date.today()
    print(f"Generating daily report for {today}...")
    records = att_proc.get_daily_report(today)
    print(f"Found {len(records)} records for today.")
    df_path = generate_daily_report(records, today)
    print(f"Daily report generated: {df_path}")
    
    start, end = get_weekly_dates()
    print(f"Generating weekly report from {start} to {end}...")
    p_records = att_proc.get_period_report(start, end)
    print(f"Found {len(p_records)} records for the period.")
    pf_path = generate_period_report(p_records, start, end, "weekly")
    print(f"Weekly report generated: {pf_path}")
    
    print("Success!")

if __name__ == "__main__":
    test_report_generation()
