"""הגדרות האפליקציה. כל הערכים נקראים ממשתני סביבה (קובץ .env בשרת)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # אבטחה: סיסמת הכניסה של השליח ומפתח לחתימת עוגיית ההתחברות
    app_password: str = field(default_factory=lambda: os.getenv("APP_PASSWORD", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    session_days: int = field(default_factory=lambda: int(os.getenv("SESSION_DAYS", "90")))
    cookie_secure: bool = field(default_factory=lambda: _bool("COOKIE_SECURE", True))

    # אחסון
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "/data")))

    # מנוע מפות (OSRM). אם הוא לא זמין, המערכת עוברת לחישוב מרחק אווירי.
    osrm_url: str = field(default_factory=lambda: os.getenv("OSRM_URL", "http://osrm:5000"))
    osrm_timeout: float = field(default_factory=lambda: float(os.getenv("OSRM_TIMEOUT", "20")))

    # המרת כתובות לקואורדינטות: nominatim (חינם) או google (דורש מפתח)
    geocoder: str = field(default_factory=lambda: os.getenv("GEOCODER", "nominatim").lower())
    google_maps_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_MAPS_API_KEY", ""))
    nominatim_url: str = field(
        default_factory=lambda: os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
    )
    nominatim_email: str = field(default_factory=lambda: os.getenv("NOMINATIM_EMAIL", ""))
    geocode_country: str = field(default_factory=lambda: os.getenv("GEOCODE_COUNTRY", "il"))

    # OCR
    ocr_langs: str = field(default_factory=lambda: os.getenv("OCR_LANGS", "heb+eng"))

    # אופטימיזציה
    optimizer_time_limit_s: int = field(
        default_factory=lambda: int(os.getenv("OPTIMIZER_TIME_LIMIT", "3"))
    )

    # הודעות ללקוחות (תשתית בלבד): none / log
    notifier: str = field(default_factory=lambda: os.getenv("NOTIFIER", "none").lower())

    @property
    def db_path(self) -> Path:
        return self.data_dir / "courier.db"


settings = Settings()
