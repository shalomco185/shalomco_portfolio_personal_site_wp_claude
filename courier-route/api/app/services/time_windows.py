"""חלונות זמן: קוד + שעות. הצבע נבחר אוטומטית מתוך פלטה קבועה, לפי סדר ההוספה."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AppSetting, TimeWindow

# ירוק, כתום, אדום (כמו בדוגמה: 17, 22, 23), ואחריהם צבעים נוספים שקל להבדיל ביניהם
PALETTE = [
    "#16A34A", "#F97316", "#DC2626", "#2563EB", "#9333EA",
    "#0891B2", "#DB2777", "#CA8A04", "#4B5563", "#65A30D",
]
DEFAULTS = [("17", "08:00", "20:00"), ("22", "10:00", "12:00"), ("23", "12:00", "14:00")]

_TIME = r"([01]?\d|2[0-3])(?:[:.]([0-5]\d))?"


def parse_range(text: str) -> tuple[str, str] | None:
    """'10:00–12:00', '10:00-12:00', '10-12', '8:00 עד 20:00' -> ('10:00', '12:00')."""
    m = re.fullmatch(rf"\s*{_TIME}\s*(?:-|–|—|עד|to)\s*{_TIME}\s*", text or "")
    if not m:
        return None
    start = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    end = f"{int(m.group(3)):02d}:{m.group(4) or '00'}"
    return (start, end) if start < end else None


def window_out(w: TimeWindow) -> dict:
    return {"code": w.code, "start": w.start, "end": w.end, "color": w.color, "label": f"{w.start}–{w.end}"}


def list_windows(db: Session) -> list[TimeWindow]:
    rows = db.scalars(select(TimeWindow)).all()
    return sorted(rows, key=lambda w: (int(w.code) if w.code.isdigit() else 10**9, w.code))


def next_color(db: Session) -> str:
    used = {w.color for w in db.scalars(select(TimeWindow))}
    for color in PALETTE:
        if color not in used:
            return color
    return PALETTE[len(used) % len(PALETTE)]


def seed_defaults(db: Session) -> None:
    """פעם אחת: 17, 22 ו-23 עם השעות והצבעים מהדוגמה."""
    if db.get(AppSetting, "time_windows_seeded"):
        return
    if not db.scalars(select(TimeWindow)).first():
        for i, (code, start, end) in enumerate(DEFAULTS):
            db.add(TimeWindow(code=code, start=start, end=end, color=PALETTE[i]))
    db.merge(AppSetting(key="time_windows_seeded", value={"ok": True}))
    db.commit()
