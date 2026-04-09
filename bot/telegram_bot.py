"""
bot/telegram_bot.py — Telegram Bot бо ReplyKeyboardMarkup
Тугмаҳои доимӣ дар поёни экран нишон дода мешаванд.
Навиштаи нав: рӯйхати баромадаҳо ва набаромадаҳо илова шуданд.
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
    CallbackQueryHandler, ContextTypes, filters,
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

# ── Callback data (InlineKeyboard-и ҳисобот) ────────────────────────
CB_DL_DAILY   = "cb_dl_daily"
CB_DL_WEEKLY  = "cb_dl_weekly"
CB_DL_MONTHLY = "cb_dl_monthly"
CB_STATUS     = "cb_status"

# ── Матни тугмаҳои Reply (точно ин матн MessageHandler-ро trigger мекунад) ──
BTN_TODAY        = "📋 Ҳозиршавии имрӯз"
BTN_LATE         = "⏰ Дермондагон"
BTN_ABSENT       = "❌ Ғоибон"
BTN_DEPARTURES   = "🚪 Рӯйхати баромадаҳо"
BTN_NOT_DEPARTED = "🏢 Набаромадагон"
BTN_DEVICES      = "🔌 Дастгоҳҳо"
BTN_REPORTS      = "📊 Ҳисобот / Excel"
BTN_HELP         = "❓ Кӯмак"


def set_processors(attendance_proc, listener_mgr=None):
    global _attendance_processor, _listener_manager
    _attendance_processor = attendance_proc
    _listener_manager = listener_mgr


def _is_admin(update: Update) -> bool:
    uid = update.effective_chat.id if update.effective_chat else None
    return uid in settings.TELEGRAM_ADMIN_CHAT_IDS


def _fmt(val: Optional[str]) -> str:
    """'2026-04-08 08:12:34' → '08:12'"""
    if not val:
        return "—"
    try:
        return val.split(" ")[1][:5]
    except Exception:
        return str(val)


# ════════════════════════════════════════════════════════
# КЛАВИАТУРҲО
# ════════════════════════════════════════════════════════

def _reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатураи доимӣ — дар поёни экран ҳамеша нишон дода мешавад.
    Сатр 1: Ҳозиршавӣ | Дермондагон | Ғоибон
    Сатр 2: Баромадаҳо | Набаромадагон | Дастгоҳҳо
    Сатр 3: Ҳисобот / Excel | Кӯмак
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(BTN_TODAY),
                KeyboardButton(BTN_LATE),
                KeyboardButton(BTN_ABSENT),
            ],
            [
                KeyboardButton(BTN_DEPARTURES),
                KeyboardButton(BTN_NOT_DEPARTED),
                KeyboardButton(BTN_DEVICES),
            ],
            [
                KeyboardButton(BTN_REPORTS),
                KeyboardButton(BTN_HELP),
            ],
        ],
        resize_keyboard=True,       # Андозаро мувофиқ кун
        # persistent=True,            # Ҳамеша нишон деҳ
        input_field_placeholder="Тугмаро пахш кунед...",
    )


def _reports_inline() -> InlineKeyboardMarkup:
    """Inline тугмаҳои Excel"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Excel рӯзона",    callback_data=CB_DL_DAILY)],
        [
            InlineKeyboardButton("📅 Excel ҳафтаина", callback_data=CB_DL_WEEKLY),
            InlineKeyboardButton("🗓 Excel моҳона",   callback_data=CB_DL_MONTHLY),
        ],
        [InlineKeyboardButton("🔌 Ҳолати дастгоҳҳо", callback_data=CB_STATUS)],
    ])


def _status_icon(status: Optional[str]) -> str:
    return {
        "present":       "✅",
        "late":          "⏰",
        "early_leave":   "🚪",
        "late_and_early":"⚠️",
        "absent":        "❌",
    }.get(status or "", "•")


def _menu_text() -> str:
    today_str = date.today().strftime("%d.%m.%Y — %A")
    return (
        f"🏫 *Системаи назорати ҳозиршавӣ*\n"
        f"📅 _{today_str}_\n\n"
        "Тугмаҳои поён барои идоракунӣ истифода баред 👇"
    )


# ════════════════════════════════════════════════════════
# /start  /menu
# ════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("⛔ Дастрасӣ рад шуд.")
        return
    await update.message.reply_text(
        _menu_text(),
        reply_markup=_reply_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    await update.message.reply_text(
        _menu_text(),
        reply_markup=_reply_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ════════════════════════════════════════════════════════
# HANDLER-И ТУГМАҲОИ REPLY
# ════════════════════════════════════════════════════════

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ҳамаи тугмаҳои Reply дар ин ҷо коркард мешаванд"""
    if not _is_admin(update):
        return

    text = update.message.text

    if text == BTN_TODAY:
        await _show_today(update)
    elif text == BTN_LATE:
        await _show_late(update)
    elif text == BTN_ABSENT:
        await _show_absent(update)
    elif text == BTN_DEPARTURES:
        await _show_departures(update)
    elif text == BTN_NOT_DEPARTED:
        await _show_not_departed(update)
    elif text == BTN_DEVICES:
        await _show_devices(update)
    elif text == BTN_REPORTS:
        await _show_reports_menu(update)
    elif text == BTN_HELP:
        await _show_help(update)


# ════════════════════════════════════════════════════════
# МАНТИҚИ ҲАР ТУГМА
# ════════════════════════════════════════════════════════

async def _show_today(update: Update):
    """📋 Ҳозиршавии имрӯз — ҳама ки омаданд"""
    if not _attendance_processor:
        await update.message.reply_text("❗ Система тайёр нест.")
        return

    records = _attendance_processor.get_today_present()
    today = date.today().strftime("%d.%m.%Y")

    if not records:
        await update.message.reply_text(
            f"📋 *Ҳозиршавии имрӯз* — {today}\n\nҲеҷ кас ҳозир нашудааст.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"📋 *Ҳозиршавии имрӯз* — {today}\n"]
    lines.append(f"_Ҳамаи кормандон: {len(records)} нафар_\n")

    for i, r in enumerate(records, 1):
        ic = _status_icon(r.get("status"))
        fi = _fmt(r.get("first_in"))
        lo = _fmt(r.get("last_out"))
        name = r["full_name"]
        pos  = r.get("position") or "—"
        late = r.get("late_minutes") or 0
        early= r.get("early_leave_min") or 0

        extra = ""
        if late  > 0: extra += f" ⏰+{late}д"
        if early > 0: extra += f" 🚪-{early}д"

        lines.append(f"{i}. {ic} *{name}*{extra}\n   _{pos}_\n   Омад: `{fi}` | Рафт: `{lo}`")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _show_late(update: Update):
    """⏰ Дермондагон"""
    if not _attendance_processor:
        await update.message.reply_text("❗ Система тайёр нест.")
        return

    records = _attendance_processor.get_today_lates()
    today = date.today().strftime("%d.%m.%Y")

    if not records:
        await update.message.reply_text(
            f"⏰ *Дермондагон* — {today}\n\n✅ Ҳеҷ кас дер накардааст!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"⏰ *Дермондагон* — {today}\n"]
    for i, r in enumerate(records, 1):
        lines.append(
            f"{i}. *{r['full_name']}*\n"
            f"   _{r.get('position') or '—'}_\n"
            f"   Омад: `{_fmt(r.get('first_in'))}` | Дерӣ: *{r.get('late_minutes', 0)} дақиқа*"
        )

    lines.append(f"\n_Ҷамъ: {len(records)} нафар_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_absent(update: Update):
    """❌ Ғоибон"""
    if not _attendance_processor:
        await update.message.reply_text("❗ Система тайёр нест.")
        return

    records = _attendance_processor.get_today_absents()
    today = date.today().strftime("%d.%m.%Y")

    if not records:
        await update.message.reply_text(
            f"❌ *Ғоибон* — {today}\n\n✅ Ҳама ҳозир шуданд!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"❌ *Ғоибон* — {today}\n"]
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. *{r['full_name']}*\n   _{r.get('position') or '—'}_")

    lines.append(f"\n_Ҷамъ: {len(records)} нафар_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_departures(update: Update):
    """
    🚪 Рӯйхати баромадаҳо —
    Ҳамаи кормандоне ки last_out дорад (баромадаанд).
    Тартиб: охирин баромада аввал.
    """
    if not _attendance_processor:
        await update.message.reply_text("❗ Система тайёр нест.")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    today_fmt = date.today().strftime("%d.%m.%Y")

    # Ҳамаи имрӯза ки last_out дорад
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
            f"🚪 *Рӯйхати баромадаҳо* — {today_fmt}\n\nҲанӯз ҳеҷ кас барнагаштааст.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"🚪 *Рӯйхати баромадаҳо* — {today_fmt}\n"]
    lines.append(f"_Баромадагон: {len(rows)} нафар_\n")

    for i, r in enumerate(rows, 1):
        early = r.get("early_leave_min") or 0
        early_str = f" ⚠️ барвақт: {early} дақ" if early > 0 else ""
        lines.append(
            f"{i}. *{r['full_name']}*\n"
            f"   _{r.get('position') or '—'}_\n"
            f"   Омад: `{_fmt(r.get('first_in'))}` | Рафт: `{_fmt(r.get('last_out'))}`{early_str}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_not_departed(update: Update):
    """
    🏢 Набаромадагон —
    Кормандоне ки first_in дорад (омадаанд) аммо last_out надорад (ҳанӯз дар корхона).
    """
    if not _attendance_processor:
        await update.message.reply_text("❗ Система тайёр нест.")
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
            f"🏢 *Набаромадагон* — {today_fmt}\n\nҲама аллакай рафтаанд.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"🏢 *Набаромадагон* — {today_fmt}\n"]
    lines.append(f"_Ҳанӯз дар корхона: {len(rows)} нафар_\n")

    for i, r in enumerate(rows, 1):
        late = r.get("late_minutes") or 0
        late_str = f" ⏰ дер: {late} дақ" if late > 0 else ""
        lines.append(
            f"{i}. *{r['full_name']}*\n"
            f"   _{r.get('position') or '—'}_\n"
            f"   Омад: `{_fmt(r.get('first_in'))}`{late_str}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_devices(update: Update):
    """🔌 Ҳолати дастгоҳҳо"""
    if not _listener_manager:
        await update.message.reply_text(
            "ℹ️ Маълумоти дастгоҳ мавҷуд нест.\n"
            "_Listener-ҳо оғоз нашудаанд._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    status = _listener_manager.status()
    lines = ["🔌 *Ҳолати дастгоҳҳо*\n"]

    for direction, info in status.items():
        icon  = "🟢" if info["connected"] else "🔴"
        state = "Васл ✓" if info["connected"] else "Қатъ ✗"
        dev_label = "ОМАДАН (IN)" if direction == "IN" else "РАФТАН (OUT)"
        lines.append(
            f"{icon} *{dev_label}*\n"
            f"   IP: `{info['ip']}`\n"
            f"   Ҳолат: _{state}_\n"
            f"   Васлшавӣ: {info['reconnect_count']} бор"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def _show_reports_menu(update: Update):
    """📊 Менюи ҳисобот — Inline тугмаҳо"""
    await update.message.reply_text(
        "📊 *Ҳисобот / Excel*\n\n"
        "Навъи ҳисобот интихоб кунед:",
        reply_markup=_reports_inline(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _show_help(update: Update):
    """❓ Кӯмак"""
    lines = [
        "❓ *Роҳнамои Bot*\n",
        "📋 *Ҳозиршавии имрӯз* — ҳама омадагон бо вақт",
        "⏰ *Дермондагон* — кӣ дер карда бо дақиқа",
        "❌ *Ғоибон* — кӣ имрӯз нашудааст",
        "🚪 *Рӯйхати баромадаҳо* — кӣ аллакай рафтааст",
        "🏢 *Набаромадагон* — кӣ ҳанӯз дар корхона аст",
        "🔌 *Дастгоҳҳо* — ҳолати дастгоҳҳои IN/OUT",
        "📊 *Ҳисобот / Excel* — файлҳои Excel барориш",
        "",
        "💡 _Ҳамаи тугмаҳо дар поёни экран доимӣ нишон дода мешаванд_",
        "",
        "⚙️ *Команда-ҳо:*",
        "/start — Менюро кушоед",
        "/menu — Менюро навсозед",
        "/today /late /absent — Маълумоти зуд",
        "/status — Дастгоҳҳо",
        "/download\\_daily — Excel рӯзона",
        "/download\\_weekly — Excel ҳафтаина",
        "/download\\_monthly — Excel моҳона",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════
# INLINE CALLBACK — Excel download + Status
# ════════════════════════════════════════════════════════

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_chat.id not in settings.TELEGRAM_ADMIN_CHAT_IDS:
        await query.answer("⛔ Дастрасӣ рад шуд.", show_alert=True)
        return

    data = query.data

    if data == CB_STATUS:
        if not _listener_manager:
            await query.edit_message_text("ℹ️ Дастгоҳҳо ёфт нашуд.")
            return
        status = _listener_manager.status()
        lines = ["🔌 *Ҳолати дастгоҳҳо*\n"]
        for direction, info in status.items():
            icon  = "🟢" if info["connected"] else "🔴"
            state = "Васл ✓" if info["connected"] else "Қатъ ✗"
            dev   = "ОМАДАН (IN)" if direction == "IN" else "РАФТАН (OUT)"
            lines.append(
                f"{icon} *{dev}*\n"
                f"   IP: `{info['ip']}` | _{state}_\n"
                f"   Васлшавӣ: {info['reconnect_count']} бор"
            )
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=_reports_inline(),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data in (CB_DL_DAILY, CB_DL_WEEKLY, CB_DL_MONTHLY):
        await _inline_download(query, data)


async def _inline_download(query, data: str):
    if not _attendance_processor:
        await query.edit_message_text("❗ Система тайёр нест.")
        return

    labels = {
        CB_DL_DAILY:   "рӯзона",
        CB_DL_WEEKLY:  "ҳафтаина",
        CB_DL_MONTHLY: "моҳона",
    }
    await query.edit_message_text(
        f"⏳ *Excel {labels[data]}* тайёр мешавад...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        if data == CB_DL_DAILY:
            today   = date.today()
            records = _attendance_processor.get_daily_report(today)
            fp      = generate_daily_report(records, today)
            caption = f"📊 Ҳисоботи рӯзона — {today.strftime('%d.%m.%Y')}"

        elif data == CB_DL_WEEKLY:
            start, end = get_weekly_dates()
            records = _attendance_processor.get_period_report(start, end)
            fp      = generate_period_report(records, start, end, "weekly")
            caption = f"📅 Ҳисоботи ҳафтаина — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"

        else:
            start, end = get_monthly_dates()
            records = _attendance_processor.get_period_report(start, end)
            fp      = generate_period_report(records, start, end, "monthly")
            caption = f"🗓 Ҳисоботи моҳона — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}"

        with open(fp, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=fp.name,
                caption=caption,
            )
        await query.edit_message_text(
            "📊 *Ҳисобот / Excel*\n\nНавъи ҳисобот интихоб кунед:",
            reply_markup=_reports_inline(),
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Report generation error: {e}")
        await query.edit_message_text(
            f"❗ Хато:\n`{str(e)[:200]}`",
            reply_markup=_reports_inline(),
            parse_mode=ParseMode.MARKDOWN,
        )


# ════════════════════════════════════════════════════════
# КОМАНДА-shortcuts (ба корбарони пешрафта)
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
    if not _is_admin(update): return
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
        caption=f"📊 Ҳисоботи рӯзона — {today.strftime('%d.%m.%Y')}",
    )

async def cmd_download_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update) or not _attendance_processor: return
    start, end = get_weekly_dates()
    records    = _attendance_processor.get_period_report(start, end)
    fp         = generate_period_report(records, start, end, "weekly")
    await update.message.reply_document(
        document=open(fp, "rb"), filename=fp.name,
        caption=f"📅 Ҳисоботи ҳафтаина — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}",
    )

async def cmd_download_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update) or not _attendance_processor: return
    start, end = get_monthly_dates()
    records    = _attendance_processor.get_period_report(start, end)
    fp         = generate_period_report(records, start, end, "monthly")
    await update.message.reply_document(
        document=open(fp, "rb"), filename=fp.name,
        caption=f"🗓 Ҳисоботи моҳона — {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}",
    )


# ════════════════════════════════════════════════════════
# NOTIFICATION SERVICE
# ════════════════════════════════════════════════════════

class NotificationService:
    """Фиристодани огоҳиҳои автоматӣ"""

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

        lines = [f"🌅 *Огоҳии субҳ — {today}*\n"]
        lines.append(f"✅ Ҳозир: *{len(records)} нафар*")

        if lates:
            lines.append(f"⏰ Дер карданд: *{len(lates)} нафар*")
            for r in lates[:5]:
                lines.append(
                    f"  • {r['full_name']} — `{_fmt(r.get('first_in'))}` "
                    f"(+{r.get('late_minutes', 0)} дақ)"
                )
        if absents:
            lines.append(f"❌ Ғоибон: *{len(absents)} нафар*")
            for r in absents[:5]:
                lines.append(f"  • {r['full_name']}")

        await self.send_message("\n".join(lines))

    async def send_evening_summary(self, attendance_proc):
        today        = date.today().strftime("%d.%m.%Y")
        records      = attendance_proc.get_today_present()
        early_leaves = [r for r in records if r.get("status") in ("early_leave", "late_and_early")]
        still_in     = [r for r in records if not r.get("last_out")]

        lines = [f"🌆 *Огоҳии бегоҳ — {today}*\n"]

        if early_leaves:
            lines.append(f"🚪 Барвақт рафтанд: *{len(early_leaves)} нафар*")
            for r in early_leaves[:5]:
                lines.append(f"  • {r['full_name']} — `{_fmt(r.get('last_out'))}`")

        if still_in:
            lines.append(f"\n🏢 Ҳанӯз дар корхона: *{len(still_in)} нафар*")
            for r in still_in[:5]:
                lines.append(f"  • {r['full_name']} — омад `{_fmt(r.get('first_in'))}`")

        await self.send_message("\n".join(lines))

    async def send_device_alert(self, direction: str, error: Exception):
        msg = (
            f"⚠️ *Огоҳии дастгоҳ!*\n\n"
            f"Дастгоҳ: *{direction}*\n"
            f"Хато: `{str(error)[:200]}`\n\n"
            f"Система кӯшиш мекунад дубора васл шавад..."
        )
        await self.send_message(msg)


# ════════════════════════════════════════════════════════
# BUILD APP
# ════════════════════════════════════════════════════════

def build_bot_app(attendance_proc, listener_mgr=None) -> Application:
    set_processors(attendance_proc, listener_mgr)

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Команда-ҳо
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

    # ReplyKeyboard тугмаҳо — матни паём тавассути MessageHandler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button))

    # Inline callback
    app.add_handler(CallbackQueryHandler(on_callback))

    return app