"""מבני הנתונים של ה-API (קלט ופלט)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    password: str


class StopIn(BaseModel):
    address: str = Field(min_length=2, max_length=300)
    address_details: str | None = Field(default=None, max_length=300)
    tracking_number: str | None = Field(default=None, max_length=60)
    time_window_code: str | None = Field(default=None, max_length=10)
    recipient: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    source: str = Field(default="manual", pattern="^(manual|ocr|bulk)$")
    raw_text: str | None = Field(default=None, max_length=5000)
    lat: float | None = Field(default=None, ge=-90, le=90)  # אם השליח בחר נקודה ידנית
    lon: float | None = Field(default=None, ge=-180, le=180)
    # הרחבה עתידית
    priority: int = 0
    time_window_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    time_window_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    volume: float | None = None


class StopPatch(BaseModel):
    address: str | None = Field(default=None, min_length=2, max_length=300)
    address_details: str | None = Field(default=None, max_length=300)
    tracking_number: str | None = Field(default=None, max_length=60)
    time_window_code: str | None = Field(default=None, max_length=10)
    recipient: str | None = None
    phone: str | None = None
    notes: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class CustomerIn(BaseModel):
    recipient: str | None = Field(default=None, max_length=120)
    phone: str = Field(min_length=9, max_length=30)
    address: str = Field(min_length=2, max_length=300)
    address_details: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class CustomerPatch(BaseModel):
    recipient: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, min_length=9, max_length=30)
    address: str | None = Field(default=None, min_length=2, max_length=300)
    address_details: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class TimeWindowIn(BaseModel):
    code: str = Field(min_length=1, max_length=10, pattern=r"^[0-9A-Za-zא-ת]+$")
    time: str = Field(min_length=3, max_length=40)  # "10:00–12:00"


class StatusIn(BaseModel):
    status: str


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str | None = None


class PlanIn(BaseModel):
    start: Point | None = None  # מיקום GPS נוכחי; אם חסר - נקודת היציאה השמורה
    end: Point | None = None  # הרחבה עתידית: נקודת סיום


class SettingsIn(BaseModel):
    start_address: str | None = Field(default=None, max_length=300)
