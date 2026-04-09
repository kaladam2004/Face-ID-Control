"""
core/event_parser.py - Парсинги event-ҳои Dahua CGI
"""
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Event-ҳои муҳим
FACE_EVENT_CODES = {"_DoorFace_", "DoorFace", "AccessControl"}
DOOR_EVENT_CODES = {"DoorStatus", "_NewFile_"}


class DahuaEvent:
    """Яке event-и Dahua"""

    def __init__(self):
        self.code: str = ""
        self.action: str = ""
        self.index: str = ""
        self.data: Dict[str, Any] = {}
        self.raw_text: str = ""

        # Аз face event
        self.user_id: Optional[str] = None
        self.similarity: Optional[float] = None
        self.alive: Optional[int] = None
        self.real_utc: Optional[str] = None
        self.door: Optional[str] = None
        self.open_method: Optional[str] = None
        self.card_no: Optional[str] = None
        self.event_time: Optional[datetime] = None

    def is_face_event(self) -> bool:
        return any(code in self.code for code in FACE_EVENT_CODES)

    def is_valid_face(self) -> bool:
        """Ин face event-и воқеӣ аст (UserID дорад)?"""
        return self.is_face_event() and bool(self.user_id)

    def __repr__(self):
        return (
            f"DahuaEvent(code={self.code}, user_id={self.user_id}, "
            f"time={self.event_time}, door={self.door})"
        )


def parse_event_block(text: str) -> Optional[DahuaEvent]:
    """
    Як блоки event-ро parse кун.

    Шакли блок:
    Code=_DoorFace_
    action=Pulse
    index=0
    data={...}
    """
    if not text.strip():
        return None

    event = DahuaEvent()
    event.raw_text = text

    for line in text.strip().splitlines():
        line = line.strip()
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if key == "Code":
            event.code = value
        elif key == "action":
            event.action = value
        elif key == "index":
            event.index = value
        elif key == "data" or key.startswith("data."):
            # Ин ҷо мумкин аст JSON ё key=value бошад
            pass

    # Data block-ро ба таври ҷудогона parse кун
    _parse_data_fields(text, event)

    return event if event.code else None


def _parse_data_fields(text: str, event: DahuaEvent):
    """Майдонҳои data. аз event блок parse кун"""
    patterns = {
        "user_id": [
            r"data\.UserID\s*=\s*(.+)",
            r"data\.FaceInfo\.UserID\s*=\s*(.+)",
            r"UserID\s*=\s*(.+)",
        ],
        "similarity": [
            r"data\.Similarity\s*=\s*(\d+\.?\d*)",
            r"Similarity\s*=\s*(\d+\.?\d*)",
        ],
        "alive": [
            r"data\.Alive\s*=\s*(\d+)",
            r"Alive\s*=\s*(\d+)",
        ],
        "real_utc": [
            r"data\.RealUTC\s*=\s*(.+)",
            r"RealUTC\s*=\s*(.+)",
        ],
        "door": [
            r"data\.Door\s*=\s*(.+)",
            r"Door\s*=\s*(.+)",
        ],
        "open_method": [
            r"data\.OpenDoorMethod\s*=\s*(.+)",
            r"OpenDoorMethod\s*=\s*(.+)",
        ],
        "card_no": [
            r"data\.CardNo\s*=\s*(.+)",
            r"CardNo\s*=\s*(.+)",
        ],
    }

    for field, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if field == "similarity":
                    try:
                        setattr(event, field, float(val))
                    except ValueError:
                        pass
                elif field == "alive":
                    try:
                        setattr(event, field, int(val))
                    except ValueError:
                        pass
                else:
                    setattr(event, field, val)
                break

    # Вақти event
    _parse_event_time(text, event)


def _parse_event_time(text: str, event: DahuaEvent):
    """Вақти event-ро parse кун"""
    # UTC timestamp
    if event.real_utc:
        try:
            ts = int(event.real_utc)
            event.event_time = datetime.utcfromtimestamp(ts)
            return
        except (ValueError, OSError):
            pass

    # Дигар форматҳо
    time_patterns = [
        r"LocalTime\s*=\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
        r"UTC\s*=\s*(\d+)",
        r"time=(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
    ]
    for pat in time_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            try:
                if val.isdigit():
                    event.event_time = datetime.utcfromtimestamp(int(val))
                else:
                    event.event_time = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                return
            except (ValueError, OSError):
                continue

    # Агар вақт нашуд, ҳоз
    event.event_time = datetime.utcnow()


class EventStreamParser:
    """
    Parser-и ҷараёни event Dahua.
    Блок-ҳо бо "--myboundary" ё "Content-Type:" ҷудо мешаванд.
    """

    BOUNDARY_PATTERNS = [
        "--myboundary",
        "--boundary",
        "Content-Type:",
        "Content-Length:",
    ]

    def __init__(self):
        self._buffer = ""

    def feed(self, data: str) -> list:
        """
        Маълумот дода мешавад, event-ҳои parse-шуда бармегарданд.
        """
        self._buffer += data
        events = []

        # Ҷустуҷӯи блок-ҳо
        blocks = self._split_blocks(self._buffer)

        for i, block in enumerate(blocks[:-1]):  # охириро нигоҳ дор
            ev = parse_event_block(block)
            if ev and ev.code:
                events.append(ev)

        if blocks:
            self._buffer = blocks[-1]

        return events

    def _split_blocks(self, text: str) -> list:
        """Матнро ба блок-ҳо ҷудо кун"""
        # Ҷустуҷӯи code= ки оғози блоки нав аст
        parts = re.split(r"(?=\bCode\s*=)", text)
        if len(parts) > 1:
            return parts
        # Агар boundary бошад
        parts = re.split(r"--(?:myboundary|boundary)\r?\n", text)
        return parts if len(parts) > 1 else [text]

    def reset(self):
        self._buffer = ""
