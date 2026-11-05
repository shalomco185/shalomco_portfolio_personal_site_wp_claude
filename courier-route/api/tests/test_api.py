import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.services import geocoding

FAKE = {
    "הרצל 1, תל אביב": (32.0625, 34.7706),
    "דיזנגוף 100, תל אביב": (32.0790, 34.7740),
    "אבן גבירול 50, תל אביב": (32.0800, 34.7810),
    "ז'בוטינסקי 10, רמת גן": (32.0860, 34.8010),
}


class FakeGeocoder:
    name = "fake"

    def geocode(self, address):
        if address in FAKE:
            lat, lon = FAKE[address]
            return geocoding.GeoResult(lat, lon, address + ", ישראל", "fake")
        return None


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(geocoding, "get_geocoder", lambda: FakeGeocoder())
    with TestClient(main.app) as c:
        yield c


def login(c):
    assert c.post("/api/login", json={"password": "test-pass"}).status_code == 200


def test_requires_login(client):
    assert client.get("/api/stops").status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401


def test_full_day_flow(client):
    login(client)
    client.post("/api/day/finish")
    ids = []
    for addr in FAKE:
        r = client.post("/api/stops", json={"address": addr}).json()
        assert r["geocode_error"] is None and r["stop"]["geocoded"]
        ids.append(r["stop"]["id"])

    bad = client.post("/api/stops", json={"address": "כתובת שלא קיימת 999"}).json()
    assert bad["geocode_error"] and not bad["stop"]["geocoded"]

    # תיקון ידני על המפה
    fixed = client.patch(f"/api/stops/{bad['stop']['id']}", json={"lat": 32.07, "lon": 34.79}).json()
    assert fixed["stop"]["geocoded"]

    route = client.post("/api/route/plan", json={"start": {"lat": 32.06, "lon": 34.77}}).json()
    assert route["engine"] == "haversine"  # OSRM לא זמין בבדיקות
    assert len(route["items"]) == 5
    assert [i["seq"] for i in route["items"]] == [1, 2, 3, 4, 5]
    assert route["items"][0]["stop"]["waze_url"].startswith("https://waze.com/ul?ll=")
    # סדר העמסה = הפוך לסדר המסירה
    assert [x["seq"] for x in route["loading_order"]] == [5, 4, 3, 2, 1]
    assert route["loading_order"][0]["load_position"] == 1

    assert client.get("/api/route/current").json()["id"] == route["id"]

    # שינוי ברשימה מבטל את המסלול הקיים
    client.delete(f"/api/stops/{ids[0]}")
    assert client.get("/api/route/current").json() is None

    assert client.post("/api/day/finish").json()["archived"] == 4
    assert client.get("/api/stops").json() == []


def test_plan_without_start_uses_saved_setting(client):
    login(client)
    client.post("/api/day/finish")
    assert client.post("/api/route/plan", json={}).status_code == 400
    client.post("/api/stops", json={"address": "הרצל 1, תל אביב"})
    assert client.post("/api/route/plan", json={}).status_code == 400
    s = client.put("/api/settings", json={"start_address": "דיזנגוף 100, תל אביב"}).json()
    assert s["start"]["lat"] == pytest.approx(32.079)
    r = client.post("/api/route/plan", json={})
    assert r.status_code == 200 and len(r.json()["items"]) == 1


def test_ocr_endpoint(client):
    import shutil

    if not shutil.which("tesseract"):
        pytest.skip("tesseract not installed")
    login(client)
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGB", (900, 300), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 40)
    except OSError:
        pytest.skip("font missing")
    d.text((20, 40), "SHIP TO:", fill="black", font=font)
    d.text((20, 110), "12 Dizengoff St", fill="black", font=font)
    d.text((20, 180), "Tel Aviv", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    r = client.post("/api/ocr", files={"image": ("l.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Dizengoff" in body["text"]
    assert any("Dizengoff" in c for c in body["candidates"])


def test_static_app_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "מסלול שליח" in r.text
    assert client.get("/sw.js").status_code == 200
    assert client.get("/manifest.webmanifest").status_code == 200
