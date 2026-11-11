import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import geocoding
from app.services.customers import normalize_phone, normalize_text

FAKE = {
    "רוגוזין 60, אשדוד": (31.80, 34.65),
    "הרצל 1, תל אביב": (32.0625, 34.7706),
    "הנשיא 8, חיפה": (32.79, 34.99),
}


class FakeGeocoder:
    name = "fake"

    def geocode(self, address):
        if address in FAKE:
            return geocoding.GeoResult(*FAKE[address], address, "fake")
        return None


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(geocoding, "get_geocoder", lambda: FakeGeocoder())
    with TestClient(main.app) as c:
        assert c.post("/api/login", json={"password": "test-pass"}).status_code == 200
        c.post("/api/day/finish")
        for row in c.get("/api/customers").json():  # כל טסט מתחיל מרשימה ריקה
            c.delete(f"/api/customers/{row['id']}")
        yield c


def test_normalizers():
    assert normalize_phone("+972 52-123 4567") == "0521234567"
    assert normalize_phone("052-1234567") == "0521234567"
    assert normalize_phone("03-555-1234") == "035551234"
    assert normalize_phone("12") is None
    assert normalize_phone("123456789") is None
    assert normalize_phone("521234567") == "0521234567"
    assert normalize_text("רח' רוגוזין 60, אשדוד") == "רוגוזין 60 אשדוד"


def test_crud_unique_phone_and_soft_delete(client):
    r = client.post("/api/customers", json={"recipient": "יוסי כהן", "phone": "052-1111111",
                                            "address": "רוגוזין 60, אשדוד", "address_details": "קומה 3"})
    assert r.status_code == 200, r.text
    cid = r.json()["customer"]["id"]
    assert r.json()["customer"]["geocoded"]

    dup = client.post("/api/customers", json={"phone": "0521111111", "address": "הרצל 1, תל אביב"})
    assert dup.status_code == 409 and "יוסי כהן" in dup.json()["detail"]
    assert client.post("/api/customers", json={"phone": "123456789x", "address": "הרצל 1, תל אביב"}).status_code == 422

    p = client.patch(f"/api/customers/{cid}", json={"notes": "קוד 1234", "address": "הרצל 1, תל אביב"}).json()
    assert p["customer"]["notes"] == "קוד 1234" and p["customer"]["lat"] == pytest.approx(32.0625)

    assert client.delete(f"/api/customers/{cid}").json()["ok"]
    assert all(c["id"] != cid for c in client.get("/api/customers").json())
    # אותו טלפון שוב: אותה רשומה חוזרת (לא כפילות)
    back = client.post("/api/customers", json={"recipient": "יוסי", "phone": "0521111111", "address": "רוגוזין 60, אשדוד"})
    assert back.status_code == 200 and back.json()["customer"]["id"] == cid


def test_search_and_add_as_stop(client):
    a = client.post("/api/customers", json={"recipient": "יוסי כהן", "phone": "0521111111", "address": "רוגוזין 60, אשדוד", "address_details": "קומה 3"}).json()["customer"]
    b = client.post("/api/customers", json={"recipient": "רינה לוי", "phone": "0542222222", "address": "רוגוזין 60, אשדוד", "address_details": "קומה 7"}).json()["customer"]
    client.post("/api/customers", json={"recipient": "דנה", "phone": "0503333333", "address": "הנשיא 8, חיפה"})

    hits = client.get("/api/customers/search", params={"q": "רוגוזין 60 אשד"}).json()
    assert {h["id"] for h in hits} == {a["id"], b["id"]}
    assert client.get("/api/customers/search", params={"q": "רח' רוגוזין"}).json()  # מתעלם מ"רח'"
    assert [h["id"] for h in client.get("/api/customers/search", params={"q": "רינה"}).json()] == [b["id"]]
    assert [h["recipient"] for h in client.get("/api/customers/search", params={"q": "0503"}).json()] == ["דנה"]

    s = client.post(f"/api/customers/{b['id']}/add-stop").json()["stop"]
    assert s["recipient"] == "רינה לוי" and s["address_details"] == "קומה 7" and s["geocoded"] and s["customer_id"] == b["id"]
    assert client.post(f"/api/customers/{b['id']}/add-stop").status_code == 409  # כבר ברשימה
    flags = {h["id"]: h["in_today"] for h in client.get("/api/customers/search", params={"q": "רוגוזין"}).json()}
    assert flags == {a["id"]: False, b["id"]: True}


def test_stop_with_phone_creates_and_updates_customer(client):
    r = client.post("/api/stops", json={"address": "הנשיא 8, חיפה", "recipient": "משה", "phone": "054-9998888", "notes": "להשאיר ליד הדלת"}).json()
    c = next(c for c in client.get("/api/customers").json() if c["phone"] == "054-9998888")
    assert r["stop"]["customer_id"] == c["id"] and c["notes"] == "להשאיר ליד הדלת" and c["delivery_count"] == 1
    client.patch(f"/api/stops/{r['stop']['id']}", json={"address_details": "דירה 4"})
    c2 = next(x for x in client.get("/api/customers").json() if x["id"] == c["id"])
    assert c2["address_details"] == "דירה 4" and c2["notes"] == "להשאיר ליד הדלת"
    # משלוח בלי טלפון לא יוצר לקוח
    n = len(client.get("/api/customers").json())
    client.post("/api/stops", json={"address": "הרצל 1, תל אביב"})
    assert len(client.get("/api/customers").json()) == n
