"""
reports/excel_report.py - Генератори ҳисоботи Excel
"""
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter

from config import settings

logger = logging.getLogger(__name__)

# --- Стилҳо ---
COLOR_HEADER_BG = "1F3864"
COLOR_HEADER_FG = "FFFFFF"
COLOR_LATE = "FFD700"
COLOR_ABSENT = "FF6B6B"
COLOR_PRESENT = "90EE90"
COLOR_EARLY = "FFA500"
COLOR_ALT_ROW = "F0F4F8"
COLOR_TOTAL_BG = "2E75B6"
COLOR_TOTAL_FG = "FFFFFF"

STATUS_LABELS = {
    "present": "✅ Ҳозир",
    "absent": "❌ Ғоиб",
    "late": "⏰ Дер",
    "early_leave": "🚪 Барвақт рафт",
    "late_and_early": "⚠️ Дер+Барвақт",
    None: "—",
}

WORKDAY_TJ = {
    "Mon": "Душанбе",
    "Tue": "Сешанбе",
    "Wed": "Чоршанбе",
    "Thu": "Панҷшанбе",
    "Fri": "Ҷумъа",
    "Sat": "Шанбе",
    "Sun": "Якшанбе",
}


def _header_fill():
    return PatternFill("solid", fgColor=COLOR_HEADER_BG)


def _header_font():
    return Font(bold=True, color=COLOR_HEADER_FG, name="Calibri", size=11)


def _border():
    thin = Side(style="thin", color="CCCCCC")
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def _center():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)


def _apply_header(ws, row: int, columns: List[str]):
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=row, column=col_idx, value=col_name)
        cell.fill = _header_fill()
        cell.font = _header_font()
        cell.alignment = _center()
        cell.border = _border()


def _row_fill(row_num: int, status: Optional[str] = None) -> PatternFill:
    if status == "absent":
        return PatternFill("solid", fgColor=COLOR_ABSENT)
    elif status == "late":
        return PatternFill("solid", fgColor=COLOR_LATE)
    elif status == "early_leave":
        return PatternFill("solid", fgColor=COLOR_EARLY)
    elif status == "late_and_early":
        return PatternFill("solid", fgColor=COLOR_LATE)
    elif row_num % 2 == 0:
        return PatternFill("solid", fgColor=COLOR_ALT_ROW)
    return PatternFill("solid", fgColor="FFFFFF")


def _fmt_time(val: Optional[str]) -> str:
    if not val:
        return "—"
    try:
        return val.split(" ")[1][:5]  # HH:MM
    except Exception:
        return str(val)


def generate_daily_report(
    records: List[Dict],
    report_date: date,
    output_dir: Path = None,
) -> Path:
    """Ҳисоботи рӯзона Excel"""
    output_dir = output_dir or settings.REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ҳозиршавии рӯзона"

    # Title
    ws.merge_cells("A1:J1")
    title_cell = ws["A1"]
    title_cell.value = f"ҲИСОБОТИ ҲОЗИРШАВӢ — {report_date.strftime('%d.%m.%Y')}"
    title_cell.font = Font(bold=True, size=14, name="Calibri", color=COLOR_HEADER_BG)
    title_cell.alignment = _center()

    ws.row_dimensions[1].height = 30

    COLS = [
        "№", "Ному насаб", "Вазифа", "Сана",
        "Вақти омадан", "Вақти рафтан",
        "Дер (дақ)", "Барвақт рафт (дақ)", "Статус", "Эзоҳ"
    ]
    _apply_header(ws, 2, COLS)

    # Данные
    totals = {"late": 0, "early": 0, "present": 0, "absent": 0}
    for idx, rec in enumerate(records, 1):
        row = 3 + idx - 1
        status = rec.get("status")
        fill = _row_fill(idx, status)

        values = [
            idx,
            rec.get("full_name", ""),
            rec.get("position", "") or "—",
            report_date.strftime("%d.%m.%Y"),
            _fmt_time(rec.get("first_in")),
            _fmt_time(rec.get("last_out")),
            rec.get("late_minutes") or 0,
            rec.get("early_leave_min") or 0,
            STATUS_LABELS.get(status, status or "—"),
            "",
        ]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.fill = fill
            cell.border = _border()
            cell.alignment = _center()
            cell.font = Font(name="Calibri", size=10)

        if status == "absent":
            totals["absent"] += 1
        elif status in ("present", "late", "early_leave", "late_and_early"):
            totals["present"] += 1
        totals["late"] += rec.get("late_minutes") or 0
        totals["early"] += rec.get("early_leave_min") or 0

    # Totals row
    total_row = 3 + len(records)
    total_fill = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    total_font = Font(bold=True, color=COLOR_TOTAL_FG, name="Calibri", size=11)
    total_vals = [
        "", "ҶАМЪ", "", "",
        f"Ҳозир: {totals['present']}", f"Ғоиб: {totals['absent']}",
        totals["late"], totals["early"], "", ""
    ]
    for col_idx, val in enumerate(total_vals, 1):
        cell = ws.cell(row=total_row, column=col_idx, value=val)
        cell.fill = total_fill
        cell.font = total_font
        cell.alignment = _center()
        cell.border = _border()

    # Ширина
    col_widths = [5, 30, 20, 12, 14, 14, 12, 16, 20, 15]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A3"

    filename = output_dir / f"daily_{report_date.strftime('%Y-%m-%d')}.xlsx"
    wb.save(str(filename))
    logger.info(f"Daily report saved: {filename}")
    return filename


def generate_period_report(
    records: List[Dict],
    start_date: date,
    end_date: date,
    report_type: str = "weekly",
    output_dir: Path = None,
) -> Path:
    """Ҳисоботи ҳафтаина / моҳона"""
    output_dir = output_dir or settings.REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    label = "ҲАФТАИНА" if report_type == "weekly" else "МОҲОНА"
    ws.title = f"Ҳисобот {label}"

    # Title
    ws.merge_cells("A1:K1")
    title_cell = ws["A1"]
    period_str = f"{start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}"
    title_cell.value = f"ҲИСОБОТИ {label} — {period_str}"
    title_cell.font = Font(bold=True, size=14, name="Calibri", color=COLOR_HEADER_BG)
    title_cell.alignment = _center()
    ws.row_dimensions[1].height = 30

    COLS = [
        "№", "Ному насаб", "Вазифа",
        "Рӯзҳои корӣ", "Ҳозир", "Ғоиб",
        "Дер (рӯз)", "Барвақт рафт (рӯз)",
        "Ҷамъи дерӣ (дақ)", "Ҷамъи барвақт (дақ)", "Эзоҳ"
    ]
    _apply_header(ws, 2, COLS)

    # Агрегатсия аз рӯи корманд
    from collections import defaultdict
    emp_stats: Dict[str, Dict] = defaultdict(lambda: {
        "full_name": "",
        "position": "",
        "total_workdays": 0,
        "present": 0,
        "absent": 0,
        "late_days": 0,
        "early_days": 0,
        "total_late_min": 0,
        "total_early_min": 0,
    })

    for rec in records:
        eid = rec.get("employee_id", "")
        s = emp_stats[eid]
        s["full_name"] = rec.get("full_name", "")
        s["position"] = rec.get("position") or "—"
        s["total_workdays"] += 1
        status = rec.get("status") or "absent"
        if status == "absent":
            s["absent"] += 1
        else:
            s["present"] += 1
        if "late" in status:
            s["late_days"] += 1
        if "early" in status:
            s["early_days"] += 1
        s["total_late_min"] += rec.get("late_minutes") or 0
        s["total_early_min"] += rec.get("early_leave_min") or 0

    grand_totals = {"workdays": 0, "present": 0, "absent": 0, "late_min": 0, "early_min": 0}
    for idx, (eid, s) in enumerate(sorted(emp_stats.items(), key=lambda x: x[1]["full_name"]), 1):
        row = 2 + idx
        fill = _row_fill(idx)
        values = [
            idx, s["full_name"], s["position"],
            s["total_workdays"], s["present"], s["absent"],
            s["late_days"], s["early_days"],
            s["total_late_min"], s["total_early_min"], ""
        ]
        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.fill = fill
            cell.border = _border()
            cell.alignment = _center()
            cell.font = Font(name="Calibri", size=10)

        grand_totals["workdays"] += s["total_workdays"]
        grand_totals["present"] += s["present"]
        grand_totals["absent"] += s["absent"]
        grand_totals["late_min"] += s["total_late_min"]
        grand_totals["early_min"] += s["total_early_min"]

    # Grand totals
    total_row = 2 + len(emp_stats) + 1
    total_fill = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    total_font = Font(bold=True, color=COLOR_TOTAL_FG, name="Calibri", size=11)
    total_vals = [
        "", "ҶАМЪ", "",
        grand_totals["workdays"], grand_totals["present"], grand_totals["absent"],
        "", "", grand_totals["late_min"], grand_totals["early_min"], ""
    ]
    for col_idx, val in enumerate(total_vals, 1):
        cell = ws.cell(row=total_row, column=col_idx, value=val)
        cell.fill = total_fill
        cell.font = total_font
        cell.alignment = _center()
        cell.border = _border()

    col_widths = [5, 30, 20, 14, 10, 10, 14, 18, 18, 20, 15]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A3"

    filename = output_dir / f"{report_type}_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}.xlsx"
    wb.save(str(filename))
    logger.info(f"Period report saved: {filename}")
    return filename


def get_weekly_dates() -> tuple:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = today
    return start, end


def get_monthly_dates() -> tuple:
    today = date.today()
    start = today.replace(day=1)
    return start, today
