"""לקוח של OSRM (מנוע המפות שרץ על השרת עם מפת ישראל).

אם OSRM לא זמין (למשל בזמן שהמפה עדיין בעיבוד), עוברים לחישוב לפי מרחק
אווירי כפול מקדם עיקול, כדי שהאפליקציה תמשיך לעבוד.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import httpx

from ..config import settings

log = logging.getLogger(__name__)

Coord = tuple[float, float]  # (lat, lon)

ROAD_FACTOR = 1.35  # כמה הדרך בפועל ארוכה מהקו האווירי בעיר
AVG_SPEED_MS = 30 / 3.6  # 30 קמ"ש ממוצע עירוני


@dataclass
class Matrix:
    durations: list[list[float]]  # שניות
    distances: list[list[float]]  # מטרים
    engine: str


def _coords_param(coords: list[Coord]) -> str:
    return ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)


def haversine_m(a: Coord, b: Coord) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _fallback_matrix(coords: list[Coord]) -> Matrix:
    n = len(coords)
    dist = [[haversine_m(coords[i], coords[j]) * ROAD_FACTOR for j in range(n)] for i in range(n)]
    dur = [[d / AVG_SPEED_MS for d in row] for row in dist]
    return Matrix(durations=dur, distances=dist, engine="haversine")


def table(coords: list[Coord]) -> Matrix:
    try:
        r = httpx.get(
            f"{settings.osrm_url}/table/v1/driving/{_coords_param(coords)}",
            params={"annotations": "duration,distance"},
            timeout=settings.osrm_timeout,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "Ok":
            raise ValueError(data.get("message", data.get("code")))
        fb = _fallback_matrix(coords)
        dur = [
            [v if v is not None else fb.durations[i][j] for j, v in enumerate(row)]
            for i, row in enumerate(data["durations"])
        ]
        dist = [
            [v if v is not None else fb.distances[i][j] for j, v in enumerate(row)]
            for i, row in enumerate(data["distances"])
        ]
        return Matrix(durations=dur, distances=dist, engine="osrm")
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("OSRM table failed, using haversine fallback: %s", exc)
        return _fallback_matrix(coords)


def route_geometry(coords: list[Coord]) -> dict | None:
    """קו המסלול לציור על המפה (GeoJSON). מחזיר None אם OSRM לא זמין."""
    if len(coords) < 2:
        return None
    try:
        r = httpx.get(
            f"{settings.osrm_url}/route/v1/driving/{_coords_param(coords)}",
            params={"overview": "full", "geometries": "geojson", "continue_straight": "false"},
            timeout=settings.osrm_timeout,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "Ok":
            return None
        return data["routes"][0]["geometry"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        log.warning("OSRM route failed: %s", exc)
        return None


def osrm_available() -> bool:
    try:
        r = httpx.get(f"{settings.osrm_url}/nearest/v1/driving/34.7818,32.0853", timeout=3)
        return r.status_code == 200
    except httpx.HTTPError:
        return False
