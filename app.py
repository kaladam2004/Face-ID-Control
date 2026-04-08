"""Entry point for the Face ID Attendance + Access Control desktop app."""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.database import init_db
from gui import AttendanceApp


def main() -> None:
    init_db()
    app = AttendanceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
