"""לקוחות: נרמול טלפון, יצירה/עדכון אוטומטי ממשלוחים, חיפוש לפי כתובת, שם או טלפון."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AppSetting, Customer, Stop

_STREET_WORDS = re.compile(r"(?:^|\s)(?:רחוב|רח'|רח׳|רח\.|שד'|שד׳|שד\.|שדרות)(?=\s|$)")


def normalize_phone(phone: str | None) -> str | None:
    """ספרות בלבד, בפורמט ישראלי מקומי: '+972 52-123 4567' -> '0521234567'. None אם לא תקין."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("972"):
        digits = "0" + digits[3:]
    if len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits
    # נייד 05X / 07X (10 ספרות) או קווי 02/03/04/08/09 (9 ספרות)
    return digits if re.fullmatch(r"0(?:[57]\d{8}|[23489]\d{7})", digits) else None


def normalize_text(text: str | None) -> str:
    """לחיפוש: בלי 'רחוב', בלי פיסוק, אותיות קטנות ורווח יחיד."""
    t = (text or "").lower()
    t = _STREET_WORDS.sub(" ", t)
    t = re.sub(r"[\"'׳״`.,;:()\[\]/\\|_\-]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def build_search_key(c: Customer) -> str:
    parts = [c.address, c.recipient, c.address_details, c.phone_norm, c.phone]
    return " " + normalize_text(" ".join(p for p in parts if p)) + " "


def customer_out(c: Customer) -> dict:
    return {
        "id": c.id,
        "recipient": c.recipient,
        "phone": c.phone,
        "address": c.address,
        "address_details": c.address_details,
        "notes": c.notes,
        "lat": c.lat,
        "lon": c.lon,
        "geocoded": c.is_geocoded,
        "geocode_label": c.geocode_label,
        "delivery_count": c.delivery_count,
        "last_delivery_at": c.last_delivery_at.isoformat() if c.last_delivery_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def find_by_phone(db: Session, phone_norm: str) -> Customer | None:
    return db.scalars(select(Customer).where(Customer.phone_norm == phone_norm)).first()


def upsert_from_stop(db: Session, stop: Stop, *, new_delivery: bool) -> Customer | None:
    """אחרי שמירת משלוח עם טלפון: יוצר או מעדכן את הלקוח ומקשר אליו את המשלוח.

    ערכים ריקים במשלוח לא מוחקים ערכים קיימים אצל הלקוח. לקוח שנמחק (מחיקה רכה)
    ומקבל משלוח חדש חוזר לרשימה.
    """
    norm = normalize_phone(stop.phone)
    if not norm:
        return None
    c = find_by_phone(db, norm)
    if c is None:
        c = Customer(phone=stop.phone, phone_norm=norm, address=stop.address)
        db.add(c)
    if c.deleted and new_delivery:
        c.deleted, c.deleted_at = False, None
    c.phone = stop.phone or c.phone
    if stop.address and stop.address != c.address and not stop.is_geocoded:
        c.lat = c.lon = c.geocode_label = None  # כתובת חדשה שעוד לא אותרה: לא להשאיר מיקום ישן
    for field in ("recipient", "address", "address_details", "notes"):
        value = getattr(stop, field)
        if value:
            setattr(c, field, value)
    if stop.is_geocoded:
        c.lat, c.lon, c.geocode_label = stop.lat, stop.lon, stop.geocode_label
    if new_delivery:
        c.delivery_count = (c.delivery_count or 0) + 1
        c.last_delivery_at = datetime.now(timezone.utc)
    c.search_key = build_search_key(c)
    db.flush()
    stop.customer_id = c.id
    return c


def search(db: Session, query: str, limit: int = 8) -> list[Customer]:
    """כל מילה בחיפוש צריכה להופיע (גם כחלק ממילה) בכתובת, בשם, בפרטים או בטלפון."""
    q = normalize_text(query)
    tokens = [t for t in q.split(" ") if t]
    digits = re.sub(r"\D", "", query)
    if not tokens:
        return []
    rows = db.scalars(select(Customer).where(Customer.deleted.is_(False))).all()
    scored: list[tuple[float, Customer]] = []
    for c in rows:
        key = c.search_key or build_search_key(c)
        if not all(t in key for t in tokens):
            if not (len(digits) >= 4 and digits in (c.phone_norm or "")):
                continue
        score = 0.0
        addr = " " + normalize_text(c.address) + " "
        for t in tokens:
            if f" {t} " in addr:
                score += 3  # מילה שלמה בכתובת
            elif f" {t}" in addr:
                score += 2  # תחילת מילה בכתובת
            elif f" {t}" in key:
                score += 1
        score += min(c.delivery_count or 0, 20) * 0.05  # לקוחות חוזרים קודם
        scored.append((score, c))
    scored.sort(key=lambda sc: (-sc[0], (sc[1].recipient or "")))
    return [c for _, c in scored[:limit]]


def backfill_from_stops(db: Session) -> int:
    """פעם אחת: בונה את רשימת הלקוחות מכל המשלוחים הקיימים (כולל הארכיון)."""
    if db.get(AppSetting, "customers_backfilled"):
        return 0
    n = 0
    for stop in db.scalars(select(Stop).where(Stop.phone.is_not(None)).order_by(Stop.id)):
        if upsert_from_stop(db, stop, new_delivery=True):
            n += 1
    db.merge(AppSetting(key="customers_backfilled", value={"stops": n}))
    db.commit()
    return n
