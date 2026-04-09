"""
config/settings.py - Марказии танзимот
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Базавии роҳи лоиҳа
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def get_env(key: str, default=None, cast=str):
    val = os.environ.get(key, default)
    if val is None:
        return None
    try:
        return cast(val)
    except (ValueError, TypeError):
        return default


class DeviceConfig:
    def __init__(self, name: str, ip: str, port: int, username: str, password: str, direction: str):
        self.name = name
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.direction = direction  # "IN" or "OUT"

    @property
    def base_url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    @property
    def event_stream_url(self) -> str:
        return f"{self.base_url}/cgi-bin/eventManager.cgi?action=attach&codes=%5BAll%5D"


class Settings:
    # --- Devices ---
    DEVICE_IN = DeviceConfig(
        name="IN_DEVICE",
        ip=get_env("DEVICE_IN_IP", "192.168.1.81"),
        port=get_env("DEVICE_IN_PORT", 443, int),
        username=get_env("DEVICE_IN_USERNAME", "admin"),
        password=get_env("DEVICE_IN_PASSWORD", "admin123"),
        direction="IN",
    )
    DEVICE_OUT = DeviceConfig(
        name="OUT_DEVICE",
        ip=get_env("DEVICE_OUT_IP", "192.168.1.80"),
        port=get_env("DEVICE_OUT_PORT", 443, int),
        username=get_env("DEVICE_OUT_USERNAME", "admin"),
        password=get_env("DEVICE_OUT_PASSWORD", "admin123"),
        direction="OUT",
    )

    # --- Database ---
    DATABASE_PATH = BASE_DIR / get_env("DATABASE_PATH", "data/attendance.db")

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = get_env("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_CHAT_IDS: list = [
        int(cid.strip())
        for cid in get_env("TELEGRAM_ADMIN_CHAT_IDS", "").split(",")
        if cid.strip().isdigit()
    ]

    # --- Attendance Rules ---
    DUPLICATE_TIMEOUT_MINUTES: int = get_env("DUPLICATE_TIMEOUT_MINUTES", 2, int)
    WORK_START_TIME: str = get_env("WORK_START_TIME", "08:00")
    WORK_END_TIME: str = get_env("WORK_END_TIME", "16:00")
    WORK_DAYS_STR: str = get_env("WORK_DAYS", "Mon,Tue,Wed,Thu,Fri")
    WORK_DAYS: list = [d.strip() for d in get_env("WORK_DAYS", "Mon,Tue,Wed,Thu,Fri").split(",")]

    # --- Timezone ---
    TIMEZONE: str = get_env("TIMEZONE", "Asia/Dushanbe")

    # --- Notifications ---
    NOTIFY_MORNING_SUMMARY: str = get_env("NOTIFY_MORNING_SUMMARY", "09:00")
    NOTIFY_LATE_CHECK: str = get_env("NOTIFY_LATE_CHECK", "08:15")
    NOTIFY_EVENING_SUMMARY: str = get_env("NOTIFY_EVENING_SUMMARY", "17:00")

    # --- Paths ---
    REPORTS_DIR = BASE_DIR / get_env("REPORTS_DIR", "exports")
    LOGS_DIR = BASE_DIR / get_env("LOGS_DIR", "logs")

    # --- Reconnect ---
    RECONNECT_DELAY_SECONDS: int = get_env("RECONNECT_DELAY_SECONDS", 10, int)
    MAX_RECONNECT_ATTEMPTS: int = get_env("MAX_RECONNECT_ATTEMPTS", 0, int)

    # --- Test Mode ---
    TEST_MODE: bool = get_env("TEST_MODE", "false").lower() == "true"

    @classmethod
    def ensure_dirs(cls):
        """Ҳамаи директорияҳои зарурӣ сохта шаванд"""
        for path in [cls.DATABASE_PATH.parent, cls.REPORTS_DIR, cls.LOGS_DIR]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
