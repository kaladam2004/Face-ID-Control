"""Entry point for the Attendance / Mini-Turnstile desktop app."""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import database as db
from gui import AttendanceApp


def main() -> None:
    db.init_db()
    app = AttendanceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
