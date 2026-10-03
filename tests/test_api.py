"""Tests for backend/geo.py and the /pantries API in backend/main.py."""

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.geo import haversine_miles

client = TestClient(main.app)

MONDAY_10AM = "2026-09-28T10:00"
SUNDAY_3AM = "2026-09-27T03:00"


# ---------- Haversine ----------

def test_same_point_is_zero_miles():
    assert haversine_miles(33.0, -96.7, 33.0, -96.7) == 0


def test_one_degree_of_latitude_is_about_69_miles():
    assert haversine_miles(33.0, -96.7, 34.0, -96.7) == pytest.approx(69.1, abs=0.1)


def test_distance_is_the_same_both_ways():
    plano_to_denton = haversine_miles(33.0198, -96.6989, 33.2148, -97.1331)
    denton_to_plano = haversine_miles(33.2148, -97.1331, 33.0198, -96.6989)
    assert plano_to_denton == pytest.approx(denton_to_plano)
    assert 25 < plano_to_denton < 30  # Plano to Denton is about 28 miles


# ---------- basic listing ----------

def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_lists_every_pantry_with_status():
    body = client.get("/pantries").json()
    assert body["count"] == len(main.PANTRIES)
    for pantry in body["pantries"]:
        assert pantry["status"] in {"open", "later_today", "closed", "appointment", "unknown"}
        assert pantry["distance_miles"] is None  # no location given


def test_frontend_is_served_at_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "PantryPilot" in response.text


@pytest.mark.parametrize("page", ["/", "/hours.html", "/ask.html"])
def test_every_page_has_the_bottom_nav(page):
    html = client.get(page).text
    for link in ('href="/"', 'href="ask.html"', 'href="hours.html"'):
        assert link in html
    assert 'aria-current="page"' in html  # the current tab is highlighted


@pytest.mark.parametrize("path", ["/style.css", "/app.js", "/hours.css", "/hours.js"])
def test_static_files_are_served(path):
    assert client.get(path).status_code == 200


# ---------- filters ----------

def test_open_now_only_returns_open_pantries():
    body = client.get("/pantries", params={"open_now": "true", "at": MONDAY_10AM}).json()
    assert body["count"] > 0
    assert all(p["status"] == "open" for p in body["pantries"])


def test_open_now_at_3am_sunday_only_24_7():
    body = client.get("/pantries", params={"open_now": "true", "at": SUNDAY_3AM}).json()
    assert [p["name"] for p in body["pantries"]] == ["McKinney Little Free Pantry"]


def test_no_id_hides_pantries_that_require_id():
    body = client.get("/pantries", params={"no_id": "true"}).json()
    assert all(p["id_required"] is not True for p in body["pantries"])
    assert body["count"] < len(main.PANTRIES)


def test_drive_thru_only_known_yes():
    body = client.get("/pantries", params={"drive_thru": "true"}).json()
    assert body["count"] > 0
    assert all(p["drive_thru"] is True for p in body["pantries"])


def test_spanish_only_known_yes():
    body = client.get("/pantries", params={"spanish": "true"}).json()
    assert body["count"] > 0
    assert all(p["spanish"] is True for p in body["pantries"])


def test_filters_combine():
    body = client.get("/pantries", params={"drive_thru": "true", "no_id": "true"}).json()
    for p in body["pantries"]:
        assert p["drive_thru"] is True and p["id_required"] is not True


# ---------- distance ----------

def test_lat_lng_adds_distance_and_sorts_nearest_first():
    # Standing right at Salvation Army Denton
    body = client.get("/pantries", params={"lat": 33.215787, "lng": -97.113428}).json()
    first = body["pantries"][0]
    assert first["name"] == "Salvation Army Denton"
    assert first["distance_miles"] == 0

    distances = [p["distance_miles"] for p in body["pantries"] if p["distance_miles"] is not None]
    assert distances == sorted(distances)


def test_pantries_without_location_go_last():
    body = client.get("/pantries", params={"lat": 33.0, "lng": -96.7}).json()
    seen_missing = False
    for p in body["pantries"]:
        if p["distance_miles"] is None:
            seen_missing = True
        else:
            assert not seen_missing, "a pantry with a distance came after one without"


def test_zip_uses_centroid(monkeypatch):
    monkeypatch.setattr(main, "ZIP_CENTROIDS", {"76201": {"lat": 33.215787, "lng": -97.113428}})
    body = client.get("/pantries", params={"zip": "76201"}).json()
    assert body["origin"]["source"] == "zip 76201"
    assert body["pantries"][0]["name"] == "Salvation Army Denton"


def test_unknown_zip_is_404(monkeypatch):
    monkeypatch.setattr(main, "ZIP_CENTROIDS", {})
    assert client.get("/pantries", params={"zip": "90210"}).status_code == 404


@pytest.mark.parametrize("params", [
    {"zip": "7507"},            # too short
    {"zip": "abcde"},           # not digits
    {"lat": 33.0},              # lat without lng
    {"lng": -96.7},             # lng without lat
    {"lat": 200, "lng": -96.7},  # impossible latitude
])
def test_bad_location_input_is_rejected(params):
    assert client.get("/pantries", params=params).status_code in (400, 422)


# ---------- volunteer opportunities ----------

def test_volunteer_hides_placeholders(tmp_path, monkeypatch):
    fake = tmp_path / "volunteer.json"
    fake.write_text('[{"name": "Real one", "url": "https://a.org"},'
                    ' {"name": "PLACEHOLDER", "placeholder": true}]')
    monkeypatch.setattr(main, "VOLUNTEER_PATH", fake)
    assert [o["name"] for o in client.get("/volunteer").json()] == ["Real one"]


def test_every_volunteer_listing_has_a_name_and_https_link():
    listings = client.get("/volunteer").json()
    assert listings, "volunteer.json has no real listings"
    for o in listings:
        assert o["name"].strip()
        assert o["url"].startswith("https://"), o["name"]


# ---------- deployment (Vercel) ----------

def test_rate_limit_uses_real_ip_on_vercel(monkeypatch):
    monkeypatch.setattr(main, "answer_question", lambda q, **kw: {"answer": "ok", "sources": []})
    monkeypatch.setattr(main, "ASK_LIMIT", 1)
    main._recent_questions.clear()
    monkeypatch.setenv("VERCEL", "1")
    first = client.post("/ask", json={"question": "hi there"}, headers={"x-real-ip": "1.1.1.1"})
    other_visitor = client.post("/ask", json={"question": "hi there"}, headers={"x-real-ip": "2.2.2.2"})
    same_visitor = client.post("/ask", json={"question": "hi there"}, headers={"x-real-ip": "1.1.1.1"})
    assert (first.status_code, other_visitor.status_code, same_visitor.status_code) == (200, 200, 429)
    main._recent_questions.clear()


def test_x_real_ip_is_ignored_when_not_on_vercel(monkeypatch):
    monkeypatch.setattr(main, "answer_question", lambda q, **kw: {"answer": "ok", "sources": []})
    monkeypatch.setattr(main, "ASK_LIMIT", 1)
    main._recent_questions.clear()
    monkeypatch.delenv("VERCEL", raising=False)
    client.post("/ask", json={"question": "hi there"}, headers={"x-real-ip": "1.1.1.1"})
    faked = client.post("/ask", json={"question": "hi there"}, headers={"x-real-ip": "9.9.9.9"})
    assert faked.status_code == 429  # a fake header can't dodge the limit locally
    main._recent_questions.clear()


def test_vercel_config_points_at_the_app():
    import json
    import tomllib
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert config["tool"]["vercel"]["entrypoint"] == "backend.main:app"
    # Every package the live site imports must be listed for Vercel too.
    live = {line.strip() for line in (root / "requirements.txt").read_text().splitlines() if line.strip()} - {"pytest"}
    assert live <= set(config["project"]["dependencies"])
    vercel = json.loads((root / "vercel.json").read_text())
    # "fastapi" makes Vercel use pyproject's entrypoint, whatever the dashboard preset says.
    # A "functions" key would be checked against the old api/ folder rules, which broke a deploy.
    assert vercel["framework"] == "fastapi"
    assert "functions" not in vercel
    ignored = (root / ".vercelignore").read_text().split()
    assert ".env" in ignored and "venv/" in ignored


# ---------- real ZIP search (Census data in data/zip_centroids.json) ----------

def test_real_zip_table_is_loaded():
    assert len(main.ZIP_CENTROIDS) > 100
    assert {"75070", "75034", "76201", "75074"} <= set(main.ZIP_CENTROIDS)


def test_zip_search_sorts_by_distance():
    body = client.get("/pantries", params={"zip": "76201"}).json()
    assert body["origin"]["source"] == "zip 76201"
    distances = [p["distance_miles"] for p in body["pantries"] if p["distance_miles"] is not None]
    assert distances == sorted(distances) and distances[0] < 3   # Denton pantries are close by


def test_zip_missing_from_census_uses_pantries_in_that_zip():
    assert "75033" not in main.ZIP_CENTROIDS
    body = client.get("/pantries", params={"zip": "75033"}).json()
    assert body["origin"]["source"] == "zip 75033 (approximate)"
    assert body["pantries"][0]["name"] == "Frisco Family Services Food Pantry"


def test_zip_outside_the_area_is_still_a_clear_404():
    response = client.get("/pantries", params={"zip": "90210"})
    assert response.status_code == 404 and "isn't in our" in response.json()["detail"]


def test_ask_passes_the_previous_question(monkeypatch):
    seen = {}
    def fake(question, previous=None, **kw):
        seen["previous"] = previous
        return {"answer": "ok", "sources": []}
    monkeypatch.setattr(main, "answer_question", fake)
    main._recent_questions.clear()
    client.post("/ask", json={"question": "what about Denton?", "previous": "pantries in Plano?"})
    assert seen["previous"] == "pantries in Plano?"
    assert client.post("/ask", json={"question": "hi there", "previous": "x" * 501}).status_code == 422
