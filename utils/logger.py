"""
utils/logger.py - Танзими logging
"""
import logging
import sys
from pathlib import Path
from config import settings


def setup_logging(log_level: str = "INFO"):
    """Logging-ро танзим кун"""
    settings.ensure_dirs()

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    root.addHandler(console_handler)

    # File handler
    log_file = settings.LOGS_DIR / "attendance.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    # Камтар verbose кун
    for noisy in ["urllib3", "requests", "httpx", "telegram", "asyncio"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.info("Logging initialized")
