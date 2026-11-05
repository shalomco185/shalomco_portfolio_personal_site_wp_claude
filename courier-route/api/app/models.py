"""טבלאות מסד הנתונים.

חלק מהשדות לא בשימוש בגרסה הבסיסית. הם קיימים כדי שאפשר יהיה להוסיף בהמשך
חלונות זמן, עדיפויות, נפח, סטטוס מסירה והודעות ללקוח בלי לשנות את מבנה הנתונים.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StopStatus:
    PENDING = "pending"  # ממתין למסירה (ברירת מחדל)
    # להרחבה עתידית:
    DELIVERED = "delivered"
    FAILED = "failed"  # לא בבית / לא נמסר
    ALL = {PENDING, DELIVERED, FAILED}


class Stop(Base):
    """משלוח אחד = עצירה אחת במסלול."""

    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # כתובת
    address: Mapped[str] = mapped_column(String(300))
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # טקסט OCR מקורי
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual / ocr / bulk
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    geocode_label: Mapped[str | None] = mapped_column(String(400), nullable=True)
    geocode_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # פרטי נמען
    recipient: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- הרחבה עתידית (לא בשימוש בגרסה הבסיסית) ---
    status: Mapped[str] = mapped_column(String(20), default=StopStatus.PENDING)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 0 רגיל, 1 אקספרס...
    tags: Mapped[list] = mapped_column(JSON, default=list)  # למשל ["קירור"]
    time_window_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "16:00"
    time_window_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)  # ליטרים / יחידות
    service_minutes: Mapped[float] = mapped_column(Float, default=2.0)  # זמן מסירה משוער
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proof_photo_path: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ארכיון: משלוחים של ימים קודמים
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    @property
    def is_geocoded(self) -> bool:
        return self.lat is not None and self.lon is not None


class Route(Base):
    """מסלול מחושב. נשמרת היסטוריה; האחרון הוא הפעיל."""

    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    start_lat: Mapped[float] = mapped_column(Float)
    start_lon: Mapped[float] = mapped_column(Float)
    start_label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    total_distance_m: Mapped[float] = mapped_column(Float, default=0)
    total_duration_s: Mapped[float] = mapped_column(Float, default=0)
    engine: Mapped[str] = mapped_column(String(20), default="osrm")  # osrm / haversine
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # GeoJSON LineString
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    items: Mapped[list[RouteItem]] = relationship(
        back_populates="route", order_by="RouteItem.seq", cascade="all, delete-orphan"
    )


class RouteItem(Base):
    __tablename__ = "route_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), index=True)
    stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)  # 1 = העצירה הראשונה
    leg_distance_m: Mapped[float] = mapped_column(Float, default=0)
    leg_duration_s: Mapped[float] = mapped_column(Float, default=0)
    eta_offset_s: Mapped[float] = mapped_column(Float, default=0)  # זמן מצטבר מתחילת המסלול

    route: Mapped[Route] = relationship(back_populates="items")
    stop: Mapped[Stop] = relationship()


class GeocodeCache(Base):
    """זיכרון של כתובות שכבר אותרו, כדי לא לפנות שוב לשירות החיצוני."""

    __tablename__ = "geocode_cache"

    query: Mapped[str] = mapped_column(String(300), primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(400))
    provider: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    """הגדרות שהשליח משנה מתוך האפליקציה (למשל נקודת יציאה קבועה)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
