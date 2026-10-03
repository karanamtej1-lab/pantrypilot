"""PantryPilot web server.

Run from the project folder:
    uvicorn backend.main:app --reload
"""

import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.ask import LLMUnavailable, answer_question
from backend.forecast import forecast
from backend.geo import haversine_miles, load_zip_centroids
from backend.hours import OPEN, status, to_local
from backend.llm import active_provider

PROJECT_DIR = Path(__file__).resolve().parent.parent
PANTRIES_PATH = PROJECT_DIR / "data" / "pantries.json"
VOLUNTEER_PATH = PROJECT_DIR / "data" / "volunteer.json"
FRONTEND_DIR = PROJECT_DIR / "frontend"

# Loaded once when the server starts. Re-run backend/convert.py and restart to refresh.
with open(PANTRIES_PATH, encoding="utf-8") as f:
    PANTRIES = json.load(f)
ZIP_CENTROIDS = load_zip_centroids()

app = FastAPI(title="PantryPilot")

# CORS lets a page on a DIFFERENT address (like a file opened straight from disk,
# or another dev server) call this API. Wide open for local testing only:
# before deploying, replace "*" with the real site address.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "pantries_loaded": len(PANTRIES), "zip_codes_loaded": len(ZIP_CENTROIDS),
            "ai_provider": active_provider()}  # "claude", "publik", or None; never the key itself


def find_origin(zip_code, lat, lng):
    """Work out the user's location from lat/lng or a ZIP code. None if neither given."""
    if (lat is None) != (lng is None):
        raise HTTPException(400, "Give both lat and lng, or neither.")
    if lat is not None:
        return {"lat": lat, "lng": lng, "source": "lat/lng"}
    if zip_code:
        if zip_code in ZIP_CENTROIDS:
            point = ZIP_CENTROIDS[zip_code]
            return {"lat": point["lat"], "lng": point["lng"], "source": f"zip {zip_code}"}
        # Some newer ZIPs (like 75033) aren't in the 2020 Census table. If we list pantries
        # in that ZIP, use the middle of them as an approximate location.
        located = [p for p in PANTRIES if p["zip"] == zip_code and p["lat"] is not None]
        if located:
            lat = sum(p["lat"] for p in located) / len(located)
            lng = sum(p["lng"] for p in located) / len(located)
            return {"lat": lat, "lng": lng, "source": f"zip {zip_code} (approximate)"}
        raise HTTPException(404, f"ZIP code {zip_code} isn't in our Collin/Denton County list.")
    return None


@app.get("/pantries")
def list_pantries(
    zip: str | None = Query(None, pattern=r"^\d{5}$", description="5-digit ZIP to measure distance from"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    open_now: bool = Query(False, description="Only pantries open for walk-ins right now"),
    no_id: bool = Query(False, description="Hide pantries known to require ID"),
    drive_thru: bool = Query(False, description="Only pantries known to have drive-thru"),
    spanish: bool = Query(False, description="Only pantries known to have Spanish speakers"),
    at: datetime | None = Query(None, description="Pretend it's this time (for testing), e.g. 2026-10-03T10:00"),
):
    origin = find_origin(zip, lat, lng)
    when = to_local(at)

    results = []
    for pantry in PANTRIES:
        pantry_status = status(pantry["schedule"], when)

        if open_now and pantry_status != OPEN:
            continue
        # For ID, blank means "unknown", so only hide pantries we KNOW require it.
        if no_id and pantry["id_required"] is True:
            continue
        # For features, only show pantries we KNOW have them.
        if drive_thru and pantry["drive_thru"] is not True:
            continue
        if spanish and pantry["spanish"] is not True:
            continue

        distance = None
        if origin and pantry["lat"] is not None and pantry["lng"] is not None:
            miles = haversine_miles(origin["lat"], origin["lng"], pantry["lat"], pantry["lng"])
            distance = round(miles, 1)

        results.append({**pantry, "status": pantry_status, "distance_miles": distance})

    if origin:
        # Nearest first; pantries with no location go at the end.
        results.sort(key=lambda p: (p["distance_miles"] is None, p["distance_miles"] or 0))

    return {
        "checked_at": when.isoformat(timespec="minutes"),
        "origin": origin,
        "count": len(results),
        "pantries": results,
    }


WeeklyTotal = Annotated[float, Field(ge=0, le=168)]  # a week only has 168 hours


class ForecastRequest(BaseModel):
    """What the Hours Coach sends. Just numbers: no names, no dates, no IDs."""
    logged_hours_this_month: float = Field(ge=0, le=744)   # 31 days x 24 h
    past_weekly_totals: list[WeeklyTotal] = Field(default_factory=list, max_length=52)
    days_left: int = Field(ge=0, le=31)
    target: float = Field(default=80, gt=0, le=744)
    what_if_extra_hours: float = Field(default=0, ge=0, le=744)


@app.post("/forecast")
def forecast_hours(request: ForecastRequest):
    """Monte Carlo estimate of the chance to reach the monthly target. Nothing is stored."""
    return forecast(
        logged_hours_this_month=request.logged_hours_this_month,
        past_weekly_totals=request.past_weekly_totals,
        days_left=request.days_left,
        target=request.target,
        what_if_extra_hours=request.what_if_extra_hours,
    )


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


# Each question costs money (or free-tier quota), so limit how often one visitor can ask.
# For a test run (tests/run_ai_eval.py) you can raise it:  ASK_RATE_LIMIT=1000 uvicorn ...
ASK_LIMIT = int(os.getenv("ASK_RATE_LIMIT", "15"))   # questions...
ASK_WINDOW_SECONDS = 600                              # ...per 10 minutes, per visitor
_recent_questions: dict[str, list[float]] = {}


def visitor_id(request):
    """Who is asking, for the rate limit.

    On Vercel every request arrives through Vercel's proxy, so the direct address is
    the proxy's, and all visitors would share one limit. Vercel puts the real
    visitor's address in the x-real-ip header. We only trust that header on Vercel
    (where VERCEL=1 is set), because locally anyone could fake it.
    """
    if os.getenv("VERCEL") and request.headers.get("x-real-ip"):
        return request.headers["x-real-ip"]
    return request.client.host if request.client else "unknown"


def seconds_until_allowed(visitor):
    """0 if this visitor may ask now (and records the question); otherwise how long to wait."""
    now = time.monotonic()
    recent = [t for t in _recent_questions.get(visitor, []) if now - t < ASK_WINDOW_SECONDS]
    if len(recent) >= ASK_LIMIT:
        _recent_questions[visitor] = recent
        return math.ceil(ASK_WINDOW_SECONDS - (now - recent[0]))  # when the oldest one expires
    _recent_questions[visitor] = recent + [now]
    return 0


@app.post("/ask")
def ask(body: AskRequest, request: Request):
    """Answer a food-help question from trusted sources only. Nothing is stored."""
    wait = seconds_until_allowed(visitor_id(request))
    if wait:
        raise HTTPException(429, "You've asked a lot of questions. Please wait a few minutes, or dial 2-1-1.",
                            headers={"Retry-After": str(wait)})
    try:
        return answer_question(body.question.strip())
    except LLMUnavailable:
        raise HTTPException(503, "The assistant isn't available right now. Please dial 2-1-1 for help.")


@app.get("/volunteer")
def volunteer_opportunities():
    """Ways to add hours, from data/volunteer.json.

    Entries marked "placeholder": true are never shown, so unfinished
    example data can't reach real users. Read on every request so edits
    to the file show up without restarting the server.
    """
    with open(VOLUNTEER_PATH, encoding="utf-8") as f:
        opportunities = json.load(f)
    return [o for o in opportunities if not o.get("placeholder")]


# Must come LAST: it catches every path the routes above didn't handle,
# so /  ->  frontend/index.html
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
