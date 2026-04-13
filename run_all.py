import sys
import asyncio
import logging
import signal
import threading
import argparse
import os
from pathlib import Path

# Роҳи лоиҳа
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from utils.logger import setup_logging
from config import settings
from core.database import DatabaseManager
from core.employees import EmployeeManager
from core.attendance import AttendanceProcessor
from listeners.dahua_listener import DahuaListener, ListenerManager
from bot.telegram_bot import build_bot_app, NotificationService
from utils.scheduler import AttendanceScheduler

setup_logging()
logger = logging.getLogger(__name__)

_shutdown_event = threading.Event()

notif_service = None
bot_loop = None


def parse_args():
    parser = argparse.ArgumentParser(description="Dahua Attendance System")
    parser.add_argument("--test-mode", action="store_true", help="Test mode (no real devices)")
    parser.add_argument("--seed", action="store_true", help="Seed test data and exit")
    parser.add_argument("--no-bot", action="store_true", help="Run without Telegram bot")
    parser.add_argument("--no-listeners", action="store_true", help="Run without device listeners")
    return parser.parse_args()


def handle_signal(signum, frame):
    logger.info(f"Signal {signum} received. Shutting down...")
    _shutdown_event.set()


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🏫 DAHUA ATTENDANCE SYSTEM v1.0                     ║
║         Системаи назорати ҳозиршавӣ                         ║
╠══════════════════════════════════════════════════════════════╣
║  ENTRY CURL: {entry:<48} ║
║  EXIT  CURL: {exit:<48} ║
║  Database: {db:<48} ║
╚══════════════════════════════════════════════════════════════╝
""".format(
        entry=(os.getenv("ENTRY_CURL_CMD", "")[:48]),
        exit=(os.getenv("EXIT_CURL_CMD", "")[:48]),
        db=str(settings.DATABASE_PATH)[:48],
    ))


def run_listeners(attendance_proc, args):
    if args.no_listeners or args.test_mode:
        logger.info("Device listeners disabled")
        return None

    def on_event(event_dict):
        try:
            direction = event_dict.get("source", "UNKNOWN")
            result = attendance_proc.process_event(event_dict, direction)
            if result:
                logger.info(f"[{direction}] Event processed for UserID={event_dict.get('user_id')}")
        except Exception as e:
            logger.exception(f"Error processing event: {e}")

    entry_cmd = os.getenv("ENTRY_CURL_CMD")
    exit_cmd = os.getenv("EXIT_CURL_CMD")

    if not entry_cmd or not exit_cmd:
        logger.error("ENTRY_CURL_CMD or EXIT_CURL_CMD not found in .env")
        return None

    mgr = ListenerManager()

    mgr.add(DahuaListener(
        name="IN",
        curl_cmd=entry_cmd,
        callback=on_event,
        reconnect_delay=settings.RECONNECT_DELAY_SECONDS,
    ))

    mgr.add(DahuaListener(
        name="OUT",
        curl_cmd=exit_cmd,
        callback=on_event,
        reconnect_delay=settings.RECONNECT_DELAY_SECONDS,
    ))

    mgr.start_all()
    logger.info("Started 2 curl-based Dahua listeners")
    return mgr


async def run_bot_async(attendance_proc, args, listener_mgr=None):
    global notif_service, bot_loop
    bot_loop = asyncio.get_event_loop()

    notif_service = NotificationService(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        admin_chat_ids=settings.TELEGRAM_ADMIN_CHAT_IDS,
    )

    sched = AttendanceScheduler(attendance_proc, notif_service, bot_loop)
    sched.setup()
    sched.run_in_thread()
    logger.info("Scheduler started")

    if args.no_bot or not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        logger.warning("Telegram bot not configured or disabled. Running without bot.")
        while not _shutdown_event.is_set():
            await asyncio.sleep(1)
        return

    app = build_bot_app(attendance_proc, listener_mgr)

    async with app:
        await app.start()
        logger.info("🤖 Telegram bot started")
        await app.updater.start_polling(drop_pending_updates=True)

        while not _shutdown_event.is_set():
            await asyncio.sleep(1)

        await app.updater.stop()
        await app.stop()
        logger.info("Bot stopped")


def main():
    args = parse_args()

    settings.ensure_dirs()
    print_banner()

    if args.seed:
        from tests.seed_data import main as seed_main
        seed_main()
        return

    if args.test_mode:
        logger.info("🧪 TEST MODE — real devices disabled")
        args.no_listeners = True

    logger.info(f"Initializing database: {settings.DATABASE_PATH}")
    db = DatabaseManager(settings.DATABASE_PATH)
    emp_mgr = EmployeeManager(db)
    att_proc = AttendanceProcessor(db, emp_mgr)

    employees = emp_mgr.get_all_active()
    if not employees:
        logger.warning("⚠️ No employees found in DB!")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    listener_mgr = run_listeners(att_proc, args)

    logger.info(f"Active employees: {len(employees)}")
    logger.info(f"Work schedule: {settings.WORK_START_TIME}–{settings.WORK_END_TIME} ({settings.WORK_DAYS_STR})")
    logger.info(f"Duplicate timeout: {settings.DUPLICATE_TIMEOUT_MINUTES} min")

    try:
        asyncio.run(run_bot_async(att_proc, args, listener_mgr))
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    finally:
        if listener_mgr:
            listener_mgr.stop_all()
        logger.info("✅ System stopped cleanly")


if __name__ == "__main__":
    main()