"""Tests for the installable app (PWA) files and for keeping the API key private."""

import json
import re
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main

client = TestClient(main.app)
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
PAGES = ["/", "/hours.html", "/ask.html"]


def png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


# ---------- manifest and icons ----------

def test_manifest_is_valid_and_installable():
    response = client.get("/manifest.json")
    assert response.status_code == 200
    manifest = response.json()
    for field in ("name", "short_name", "start_url", "display", "icons", "theme_color", "background_color"):
        assert manifest[field]
    assert manifest["display"] == "standalone"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes                      # what Chrome needs to offer "Install"
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])


def test_every_manifest_icon_exists_with_the_right_size():
    for icon in client.get("/manifest.json").json()["icons"]:
        response = client.get(icon["src"])
        assert response.status_code == 200, icon["src"]
        if icon["type"] == "image/png":
            width, height = png_size(response.content)
            assert f"{width}x{height}" == icon["sizes"], icon["src"]


def test_apple_touch_icon_is_180px():
    assert png_size(client.get("/icons/apple-touch-icon.png").content) == (180, 180)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_links_manifest_and_icons(page):
    html = client.get(page).text
    assert '<link rel="manifest" href="manifest.json">' in html
    assert 'href="icons/icon.svg"' in html
    assert 'href="icons/apple-touch-icon.png"' in html


@pytest.mark.parametrize("page", PAGES)
def test_every_file_a_page_links_to_exists(page):
    html = client.get(page).text
    for ref in re.findall(r'(?:href|src)="([^"#:]+)"', html):   # local files only (no http:, tel:)
        path = "/" + ref.lstrip("/")
        assert client.get(path).status_code == 200, f"{page} links to missing {path}"


# ---------- service worker ----------

def test_service_worker_is_served_as_javascript_from_the_root():
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]   # browsers refuse other types


def sw_list(name):
    source = (FRONTEND / "sw.js").read_text()
    block = re.search(rf"const {name} = \[(.*?)\];", source, re.DOTALL).group(1)
    return re.findall(r'"([^"]+)"', block)


def test_every_precached_file_exists():
    # One missing file makes the whole offline install fail, so check them all.
    for path in sw_list("APP_SHELL"):
        assert client.get(path).status_code == 200, path


def test_offline_data_urls_exist():
    for path in sw_list("DATA_URLS"):
        assert client.get(path).status_code == 200, path


def test_service_worker_never_caches_questions_or_forecasts():
    source = (FRONTEND / "sw.js").read_text()
    assert 'if (request.method !== "GET") return;' in source   # POST /ask and /forecast pass through


# ---------- the API key stays secret ----------

def test_publik_key_is_never_sent_to_the_browser(monkeypatch):
    secret = "pk_live_TEST_SECRET_should_never_appear"
    monkeypatch.setenv("PUBLIK_API_KEY", secret)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    paths = PAGES + ["/health", "/pantries", "/volunteer", "/manifest.json", "/sw.js", "/openapi.json"]
    paths += ["/" + p.name for p in FRONTEND.glob("*.js")] + ["/" + p.name for p in FRONTEND.glob("*.css")]
    for path in paths:
        assert secret not in client.get(path).text, path
    assert client.get("/health").json()["ai_provider"] == "publik"   # says WHICH, never the key


def test_no_key_is_hard_coded_in_the_project():
    root = FRONTEND.parent
    files = [p for d in ("backend", "frontend", "scripts") for p in (root / d).rglob("*") if p.is_file()]
    files += [root / name for name in ("vercel.json", "pyproject.toml", "requirements.txt", ".env.example")]
    for path in files:
        if path.suffix in {".png", ".pyc"}:
            continue
        text = path.read_text(errors="ignore")
        assert not re.search(r"pk_live_[A-Za-z0-9]{8,}|gsk_[A-Za-z0-9]{8,}|sk-ant-[A-Za-z0-9-]{8,}", text), path
