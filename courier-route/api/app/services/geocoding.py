"""המרת כתובת לקואורדינטות.

ברירת מחדל: Nominatim (OpenStreetMap), חינם. מגבלת שימוש: בקשה אחת בשנייה,
ולכן יש כאן תור ומטמון. אפשרות: Google Geocoding (מדויק יותר בעברית), אם
מגדירים GEOCODER=google ו-GOOGLE_MAPS_API_KEY.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import GeocodeCache
from .address_parser import normalize_address

USER_AGENT = "courier-route-app/1.0 (self-hosted single-courier route planner)"


@dataclass
class GeoResult:
    lat: float
    lon: float
    label: str
    provider: str
    approximate: bool = False


class GeocodeError(Exception):
    pass


class NominatimGeocoder:
    name = "nominatim"
    _lock = threading.Lock()
    _last_call = 0.0

    def _get(self, params: dict) -> list:
        with self._lock:  # לכל היותר בקשה אחת בשנייה
            wait = 1.1 - (time.monotonic() - NominatimGeocoder._last_call)
            if wait > 0:
                time.sleep(wait)
            NominatimGeocoder._last_call = time.monotonic()
            if settings.nominatim_email:
                params["email"] = settings.nominatim_email
            r = httpx.get(
                f"{settings.nominatim_url.rstrip('/')}/search",
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "he,en"},
                timeout=15,
            )
        r.raise_for_status()
        return r.json()

    def geocode(self, address: str) -> GeoResult | None:
        params = {"q": address, "format": "jsonv2", "limit": 1, "addressdetails": 0}
        if settings.geocode_country:
            params["countrycodes"] = settings.geocode_country
        data = self._get(dict(params))
        if not data:
            return None
        hit = data[0]
        approximate = hit.get("addresstype") not in {"house", "building", "place"} and hit.get(
            "type"
        ) not in {"house", "residential", "apartments", "building"}
        return GeoResult(
            lat=float(hit["lat"]),
            lon=float(hit["lon"]),
            label=hit.get("display_name", address),
            provider=self.name,
            approximate=approximate,
        )


class GoogleGeocoder:
    name = "google"

    def geocode(self, address: str) -> GeoResult | None:
        params = {"address": address, "key": settings.google_maps_api_key, "language": "iw"}
        if settings.geocode_country:
            params["components"] = f"country:{settings.geocode_country.upper()}"
        r = httpx.get("https://maps.googleapis.com/maps/api/geocode/json", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "ZERO_RESULTS":
            return None
        if data.get("status") != "OK":
            raise GeocodeError(f"Google: {data.get('status')} {data.get('error_message', '')}")
        hit = data["results"][0]
        loc = hit["geometry"]["location"]
        return GeoResult(
            lat=loc["lat"],
            lon=loc["lng"],
            label=hit.get("formatted_address", address),
            provider=self.name,
            approximate=hit["geometry"].get("location_type") not in {"ROOFTOP", "RANGE_INTERPOLATED"},
        )


def get_geocoder():
    if settings.geocoder == "google" and settings.google_maps_api_key:
        return GoogleGeocoder()
    return NominatimGeocoder()


def geocode(db: Session, address: str) -> GeoResult | None:
    """מחזיר תוצאה מהמטמון אם קיימת, אחרת פונה לשירות ושומר."""
    query = normalize_address(address) or address.strip()
    key = query.lower()
    cached = db.get(GeocodeCache, key)
    if cached:
        return GeoResult(cached.lat, cached.lon, cached.label, cached.provider + ":cache")

    geocoder = get_geocoder()
    try:
        res = geocoder.geocode(query)
    except httpx.HTTPError as exc:
        raise GeocodeError(f"שירות איתור הכתובות לא זמין: {exc}") from exc
    if res is None:
        return None
    db.merge(GeocodeCache(query=key, lat=res.lat, lon=res.lon, label=res.label, provider=res.provider))
    db.commit()
    return res
