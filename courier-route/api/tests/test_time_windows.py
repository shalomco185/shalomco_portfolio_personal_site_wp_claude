import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.time_windows import parse_range


@pytest.fixture()
def client():
    with TestClient(main.app) as c:
        assert c.post("/api/login", json={"password": "test-pass"}).status_code == 200
        c.post("/api/day/finish")
        yield c


def test_parse_range():
    assert parse_range("10:00–12:00") == ("10:00", "12:00")
    assert parse_range("10:00-12:00") == ("10:00", "12:00")
    assert parse_range("8-20") == ("08:00", "20:00")
    assert parse_range("8:30 עד 9:15") == ("08:30", "09:15")
    assert parse_range("12:00-10:00") is None
    assert parse_range("בוקר") is None


def test_defaults_add_update_delete(client):
    ws = {w["code"]: w for w in client.get("/api/time-windows").json()}
    assert ws["17"]["label"] == "08:00–20:00" and ws["17"]["color"] == "#16A34A"
    assert ws["22"]["label"] == "10:00–12:00" and ws["22"]["color"] == "#F97316"
    assert ws["23"]["label"] == "12:00–14:00" and ws["23"]["color"] == "#DC2626"

    new = client.post("/api/time-windows", json={"code": "31", "time": "16:00–18:00"}).json()
    assert new["label"] == "16:00–18:00" and new["color"] not in {w["color"] for w in ws.values()}
    upd = client.post("/api/time-windows", json={"code": "31", "time": "16-19"}).json()
    assert upd["label"] == "16:00–19:00" and upd["color"] == new["color"]  # עדכון שעות, אותו צבע
    assert client.post("/api/time-windows", json={"code": "32", "time": "לא שעה"}).status_code == 422
    assert client.delete("/api/time-windows/31").json()["ok"]
    assert "31" not in {w["code"] for w in client.get("/api/time-windows").json()}


def test_stop_time_window(client):
    s = client.post("/api/stops", json={"address": "x1", "lat": 32.0, "lon": 34.8, "time_window_code": "22"}).json()["stop"]
    assert (s["time_window_code"], s["time_window_start"], s["time_window_end"]) == ("22", "10:00", "12:00")
    s2 = client.patch(f"/api/stops/{s['id']}", json={"time_window_code": "23"}).json()["stop"]
    assert s2["time_window_start"] == "12:00"
    s3 = client.patch(f"/api/stops/{s['id']}", json={"time_window_code": None}).json()["stop"]
    assert s3["time_window_code"] is None and s3["time_window_start"] is None
    assert client.patch(f"/api/stops/{s['id']}", json={"time_window_code": "99"}).status_code == 422
