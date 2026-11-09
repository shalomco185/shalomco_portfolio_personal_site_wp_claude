"""שרת האפליקציה: API + הגשת אפליקציית הרשת (PWA)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import auth
from .config import settings
from .db import get_db, init_db
from .models import AppSetting, Route, RouteItem, Stop, StopStatus
from .schemas import LoginIn, PlanIn, SettingsIn, StatusIn, StopIn, StopPatch
from .services import events, routing
from .services.address_parser import parse_label
from .services.constraints import build_constraints
from .services.geocoding import GeocodeError, geocode
from .services.optimizer import OptimizerStop, Problem, build_coords, solve

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("courier")

STATIC_DIR = Path(__file__).parent / "static"
MAX_IMAGE_BYTES = 12 * 1024 * 1024

@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.app_password or not settings.secret_key:
        log.warning("APP_PASSWORD / SECRET_KEY are not set - login is disabled")
    init_db()
    yield


app = FastAPI(title="Courier Route", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def no_stale_app_files(request, call_next):
    """קבצי האפליקציה תמיד נבדקים מול השרת, כדי שהטלפון יקבל עדכונים מיד."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


login_required = [Depends(auth.require_login)]


# ---------- עזרים ----------

def waze_url(lat: float, lon: float) -> str:
    return f"https://waze.com/ul?ll={lat:.6f},{lon:.6f}&navigate=yes&zoom=17"


def stop_out(s: Stop) -> dict:
    return {
        "id": s.id,
        "address": s.address,
        "address_details": s.address_details,
        "recipient": s.recipient,
        "phone": s.phone,
        "notes": s.notes,
        "source": s.source,
        "lat": s.lat,
        "lon": s.lon,
        "geocoded": s.is_geocoded,
        "geocode_label": s.geocode_label,
        "geocode_provider": s.geocode_provider,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "waze_url": waze_url(s.lat, s.lon) if s.is_geocoded else None,
    }


def route_out(r: Route) -> dict:
    items = [
        {
            "seq": it.seq,
            "leg_distance_m": round(it.leg_distance_m),
            "leg_duration_s": round(it.leg_duration_s),
            "eta_offset_s": round(it.eta_offset_s),
            "stop": stop_out(it.stop),
        }
        for it in r.items
    ]
    return {
        "id": r.id,
        "created_at": r.created_at.isoformat(),
        "start": {"lat": r.start_lat, "lon": r.start_lon, "label": r.start_label},
        "total_distance_m": round(r.total_distance_m),
        "total_duration_s": round(r.total_duration_s),
        "engine": r.engine,
        "geometry": r.geometry,
        "items": items,
        # סדר העמסה: מה שנמסר אחרון נכנס ראשון (לעומק הרכב)
        "loading_order": [
            {"load_position": i + 1, "seq": it["seq"], "stop": it["stop"]}
            for i, it in enumerate(reversed(items))
        ],
    }


def _apply_geocode(db: Session, stop: Stop) -> str | None:
    """מאתר את הכתובת ומעדכן את העצירה. מחזיר הודעת שגיאה או None."""
    try:
        res = geocode(db, stop.address)
    except GeocodeError as exc:
        return str(exc)
    if res is None:
        stop.lat = stop.lon = None
        stop.geocode_label = None
        return "הכתובת לא נמצאה במפה. נסה לנסח אחרת (רחוב, מספר, עיר) או לבחור נקודה במפה."
    stop.lat, stop.lon = res.lat, res.lon
    stop.geocode_label = res.label
    stop.geocode_provider = res.provider
    return None


def _get_setting(db: Session, key: str) -> dict:
    row = db.get(AppSetting, key)
    return dict(row.value) if row else {}


def _invalidate_routes(db: Session) -> None:
    """שינוי ברשימת המשלוחים הופך את המסלול הקיים ללא עדכני."""
    for r in db.scalars(select(Route).where(Route.archived.is_(False))):
        r.archived = True


# ---------- ציבורי ----------

@app.get("/api/health")
def health() -> dict:
    import shutil

    return {
        "ok": True,
        "osrm": routing.osrm_available(),
        "geocoder": "google" if settings.geocoder == "google" and settings.google_maps_api_key else "nominatim",
        "ocr": shutil.which("tesseract") is not None,
        "login_configured": bool(settings.app_password and settings.secret_key),
    }


@app.post("/api/login")
def login(body: LoginIn, response: Response) -> dict:
    if not auth.check_password(body.password):
        raise HTTPException(status_code=401, detail="סיסמה שגויה")
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.make_token(),
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


# ---------- משלוחים ----------

@app.get("/api/me", dependencies=login_required)
def me() -> dict:
    return {"ok": True}


@app.get("/api/stops", dependencies=login_required)
def list_stops(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Stop).where(Stop.archived.is_(False)).order_by(Stop.id))
    return [stop_out(s) for s in rows]


@app.post("/api/stops", dependencies=login_required)
def create_stop(body: StopIn, db: Session = Depends(get_db)) -> dict:
    stop = Stop(**body.model_dump(exclude={"lat", "lon"}))
    stop.address = body.address.strip()
    error = None
    if body.lat is not None and body.lon is not None:
        stop.lat, stop.lon, stop.geocode_provider = body.lat, body.lon, "manual"
        stop.geocode_label = stop.address
    else:
        error = _apply_geocode(db, stop)
    db.add(stop)
    _invalidate_routes(db)
    db.commit()
    return {"stop": stop_out(stop), "geocode_error": error}


@app.patch("/api/stops/{stop_id}", dependencies=login_required)
def update_stop(stop_id: int, body: StopPatch, db: Session = Depends(get_db)) -> dict:
    stop = db.get(Stop, stop_id)
    if not stop or stop.archived:
        raise HTTPException(404, "המשלוח לא נמצא")
    data = body.model_dump(exclude_unset=True)
    error = None
    for key in ("recipient", "phone", "notes", "address_details"):
        if key in data:
            setattr(stop, key, data[key])
    if data.get("lat") is not None and data.get("lon") is not None:
        stop.lat, stop.lon, stop.geocode_provider = data["lat"], data["lon"], "manual"
        if data.get("address"):
            stop.address = data["address"].strip()
        stop.geocode_label = stop.address
        _invalidate_routes(db)
    elif data.get("address") and data["address"].strip() != stop.address:
        stop.address = data["address"].strip()
        error = _apply_geocode(db, stop)
        _invalidate_routes(db)
    db.commit()
    return {"stop": stop_out(stop), "geocode_error": error}


@app.delete("/api/stops/{stop_id}", dependencies=login_required)
def delete_stop(stop_id: int, db: Session = Depends(get_db)) -> dict:
    stop = db.get(Stop, stop_id)
    if not stop:
        raise HTTPException(404, "המשלוח לא נמצא")
    _invalidate_routes(db)
    db.flush()
    db.query(RouteItem).filter(RouteItem.stop_id == stop_id).delete()
    db.delete(stop)
    db.commit()
    return {"ok": True}


@app.post("/api/stops/{stop_id}/status", dependencies=login_required)
def set_status(stop_id: int, body: StatusIn, db: Session = Depends(get_db)) -> dict:
    """הרחבה עתידית (נמסר / לא בבית). קיים ב-API, לא מוצג בממשק."""
    if body.status not in StopStatus.ALL:
        raise HTTPException(400, "סטטוס לא חוקי")
    stop = db.get(Stop, stop_id)
    if not stop:
        raise HTTPException(404, "המשלוח לא נמצא")
    old = stop.status
    stop.status = body.status
    stop.status_changed_at = datetime.now(timezone.utc)
    db.commit()
    events.emit("stop_status_changed", stop=stop, old=old, new=body.status)
    return {"stop": stop_out(stop)}


@app.post("/api/day/finish", dependencies=login_required)
def finish_day(db: Session = Depends(get_db)) -> dict:
    """מעביר את כל המשלוחים והמסלולים של היום לארכיון."""
    n = 0
    for s in db.scalars(select(Stop).where(Stop.archived.is_(False))):
        s.archived = True
        n += 1
    _invalidate_routes(db)
    db.commit()
    return {"archived": n}


# ---------- OCR וכתובות ----------

@app.post("/api/ocr", dependencies=login_required)
async def ocr_label(image: UploadFile = File(...)) -> dict:
    from fastapi.concurrency import run_in_threadpool

    from .services.ocr import extract_text

    data = await image.read()
    if not data:
        raise HTTPException(400, "לא התקבלה תמונה")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "התמונה גדולה מדי")
    try:
        text = await run_in_threadpool(extract_text, data)
    except Exception as exc:  # תמונה פגומה / tesseract חסר
        log.exception("OCR failed")
        raise HTTPException(422, f"לא הצלחתי לקרוא את התמונה: {exc}") from exc
    parsed = parse_label(text)
    return {
        "text": text,
        "candidates": parsed.candidates,
        "phone": parsed.phone,
        "recipient": parsed.recipient,
        "details": parsed.details,
    }


@app.get("/api/geocode", dependencies=login_required)
def geocode_preview(q: str, db: Session = Depends(get_db)) -> dict:
    try:
        res = geocode(db, q)
    except GeocodeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not res:
        return {"found": False}
    return {"found": True, "lat": res.lat, "lon": res.lon, "label": res.label, "approximate": res.approximate}


# ---------- הגדרות ----------

@app.get("/api/settings", dependencies=login_required)
def get_settings(db: Session = Depends(get_db)) -> dict:
    return {"start": _get_setting(db, "start") or None}


@app.put("/api/settings", dependencies=login_required)
def put_settings(body: SettingsIn, db: Session = Depends(get_db)) -> dict:
    if not body.start_address:
        row = db.get(AppSetting, "start")
        if row:
            db.delete(row)
        db.commit()
        return {"start": None}
    try:
        res = geocode(db, body.start_address)
    except GeocodeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not res:
        raise HTTPException(422, "כתובת היציאה לא נמצאה במפה")
    value = {"address": body.start_address, "lat": res.lat, "lon": res.lon, "label": res.label}
    db.merge(AppSetting(key="start", value=value))
    db.commit()
    return {"start": value}


# ---------- מסלול ----------

@app.get("/api/route/current", dependencies=login_required)
def current_route(db: Session = Depends(get_db)) -> dict | None:
    r = db.scalars(
        select(Route).where(Route.archived.is_(False)).order_by(Route.id.desc()).limit(1)
    ).first()
    return route_out(r) if r else None


@app.post("/api/route/plan", dependencies=login_required)
def plan_route(body: PlanIn, db: Session = Depends(get_db)) -> dict:
    if body.start:
        start = (body.start.lat, body.start.lon)
        start_label = body.start.label or "המיקום שלי"
    else:
        saved = _get_setting(db, "start")
        if not saved:
            raise HTTPException(
                400, "אין נקודת יציאה: אפשר גישה למיקום בטלפון או הגדר כתובת יציאה בהגדרות"
            )
        start, start_label = (saved["lat"], saved["lon"]), saved.get("address")

    all_stops = list(
        db.scalars(
            select(Stop)
            .where(Stop.archived.is_(False), Stop.status == StopStatus.PENDING)
            .order_by(Stop.id)
        )
    )
    stops = [s for s in all_stops if s.is_geocoded]
    skipped = [stop_out(s) for s in all_stops if not s.is_geocoded]
    if not stops:
        raise HTTPException(400, "אין משלוחים עם כתובת מאותרת לחישוב מסלול")

    problem = Problem(
        start=start,
        stops=[OptimizerStop(stop_id=s.id, coord=(s.lat, s.lon), service_s=s.service_minutes * 60) for s in stops],
        end=(body.end.lat, body.end.lon) if body.end else None,
    )
    problem.constraints = build_constraints(problem)
    coords = build_coords(problem)
    matrix = routing.table(coords)
    solution = solve(problem, matrix)

    _invalidate_routes(db)
    route = Route(start_lat=start[0], start_lon=start[1], start_label=start_label, engine=matrix.engine)
    prev_node, eta, total_d, total_t = 0, 0.0, 0.0, 0.0
    for seq, k in enumerate(solution.order, start=1):
        node = k + 1
        leg_t = matrix.durations[prev_node][node]
        leg_d = matrix.distances[prev_node][node]
        eta += leg_t
        route.items.append(
            RouteItem(stop_id=stops[k].id, seq=seq, leg_distance_m=leg_d, leg_duration_s=leg_t, eta_offset_s=eta)
        )
        eta += problem.stops[k].service_s
        total_d += leg_d
        total_t += leg_t
        prev_node = node
    route.total_distance_m, route.total_duration_s = total_d, total_t

    ordered_coords = [start] + [problem.stops[k].coord for k in solution.order]
    if problem.end:
        ordered_coords.append(problem.end)
    route.geometry = routing.route_geometry(ordered_coords) if matrix.engine == "osrm" else None

    db.add(route)
    db.commit()
    db.refresh(route)
    events.emit("route_planned", route=route)
    out = route_out(route)
    out["skipped"] = skipped
    return out


# ---------- אפליקציית הרשת ----------

@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
