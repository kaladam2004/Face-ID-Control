"""
utils/scheduler.py - Scheduler барои огоҳиҳои автоматӣ
"""
import asyncio
import logging
import schedule
import threading
import time
from datetime import date
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class AttendanceScheduler:
    """Scheduler барои вазифаҳои мунтазам"""

    def __init__(self, attendance_proc, notification_service, loop: asyncio.AbstractEventLoop):
        self.att = attendance_proc
        self.notif = notification_service
        self.loop = loop
        self._running = False

    def _run_async(self, coro):
        """Coroutine-ро дар event loop-и мавҷуда иҷро кун"""
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def setup(self):
        """Ҳамаи вазифаҳои мунтазамро танзим кун"""

        # Огоҳии субҳ
        schedule.every().day.at(settings.NOTIFY_MORNING_SUMMARY).do(
            lambda: self._run_async(self.notif.send_morning_summary(self.att))
        )

        # Санҷиши дермонӣ
        schedule.every().day.at(settings.NOTIFY_LATE_CHECK).do(
            self._check_lates
        )

        # Огоҳии бегоҳ
        schedule.every().day.at(settings.NOTIFY_EVENING_SUMMARY).do(
            lambda: self._run_async(self.notif.send_evening_summary(self.att))
        )

        # Ғоибонро ҳисоб кун — ҳар рӯз соати 23:55
        schedule.every().day.at("23:55").do(self._mark_absents)

        logger.info(
            f"Scheduler configured: "
            f"morning={settings.NOTIFY_MORNING_SUMMARY}, "
            f"late_check={settings.NOTIFY_LATE_CHECK}, "
            f"evening={settings.NOTIFY_EVENING_SUMMARY}"
        )

    def _check_lates(self):
        lates = self.att.get_today_lates()
        if lates:
            self._run_async(self.notif.send_morning_summary(self.att))

    def _mark_absents(self):
        today = date.today()
        try:
            self.att.mark_absent_for_date(today)
            logger.info(f"Absent marking done for {today}")
        except Exception as e:
            logger.error(f"Error marking absents: {e}")

    def run_in_thread(self):
        """Scheduler-ро дар thread-и ҷудогона иҷро кун"""
        self._running = True

        def _loop():
            while self._running:
                try:
                    schedule.run_pending()
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                time.sleep(30)

        t = threading.Thread(target=_loop, daemon=True, name="AttendanceScheduler")
        t.start()
        logger.info("Scheduler thread started")
        return t

    def stop(self):
        self._running = False
        schedule.clear()
