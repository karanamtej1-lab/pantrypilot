"""Convert data/pantries.csv into data/pantries.json.

Run from the project folder:
    python backend/convert.py

Each pantry's messy `hours_text` becomes a structured `schedule`
(see data/SCHEDULE_FORMAT.md). The parser only accepts patterns it fully
understands. Anything else is FLAGGED: the pantry gets {"type": "unknown"}
(the app shows "Call for hours") and is listed at the end so a person can
write its schedule by hand in data/schedule_overrides.json.
"""

import csv
import json
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))  # so `python backend/convert.py` can import backend.hours

from backend.hours import DAY_NAMES, validate_schedule  # noqa: E402

CSV_PATH = PROJECT_DIR / "data" / "pantries.csv"
JSON_PATH = PROJECT_DIR / "data" / "pantries.json"
OVERRIDES_PATH = PROJECT_DIR / "data" / "schedule_overrides.json"

# Walk-in hours outside this range are probably a parsing mistake.
EARLIEST_HOUR = 6
LATEST_HOUR = 22

DAY = r"(?:mon|tue|wed|thu|fri|sat|sun)"
ORDINAL = r"(?:1st|2nd|3rd|4th|5th|last)"
LIST_SEPARATOR = r"\s*(?:&|/|,|\band\b)\s*"

# Optional "1st & 3rd", then days like "Mon", "Mon-Fri", "Tue & Thu", "Mon, Wed, Fri".
DAY_SPEC = re.compile(
    rf"^(?:(?P<ordinals>{ORDINAL}(?:{LIST_SEPARATOR}{ORDINAL})*)\s+)?"
    rf"(?P<days>{DAY}(?:\s*(?:-|&|/|,|\band\b)\s*{DAY})*)\b",
    re.IGNORECASE,
)

# "9am-12pm", "9-11:30am", "4:30-6:30pm", "12-4pm"
TIME_RANGE = re.compile(
    r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$",
    re.IGNORECASE,
)

# Extra words that are fine to keep as notes (they don't change the hours).
NOTE_WORDS = ["drive-through", "drive-thru", "curbside"]
VISIT_LIMIT = re.compile(r"visits?/|once/", re.IGNORECASE)


class NotConfident(Exception):
    """Raised when hours_text doesn't match a pattern we fully understand."""


# ---------- small helpers ----------

def to_24_hour(hour, minute, meridiem):
    """(4, 30, "pm") -> "16:30"."""
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def parse_time_range(text):
    """Turn "9-11:30am" into {"start": "09:00", "end": "11:30"}."""
    match = TIME_RANGE.match(text.strip())
    if not match:
        raise NotConfident(f"can't read time range {text!r}")

    start_h, start_m, start_ampm, end_h, end_m, end_ampm = match.groups()
    start_h, end_h = int(start_h), int(end_h)
    start_m, end_m = int(start_m or 0), int(end_m or 0)
    start_ampm = start_ampm.lower() if start_ampm else None
    end_ampm = end_ampm.lower() if end_ampm else None

    if end_ampm is None:
        raise NotConfident(f"no am/pm on closing time in {text!r}")

    if start_ampm is None:
        # "9-11am" -> start shares the end's am/pm... unless that puts the
        # start after the end: "11-2pm" means 11am, not 11pm.
        start_ampm = end_ampm
        if to_24_hour(start_h, start_m, start_ampm) >= to_24_hour(end_h, end_m, end_ampm):
            start_ampm = "am"

    start = to_24_hour(start_h, start_m, start_ampm)
    end = to_24_hour(end_h, end_m, end_ampm)
    if start >= end:
        raise NotConfident(f"closing time is before opening time in {text!r}")
    if not (f"{EARLIEST_HOUR:02d}:00" <= start and end <= f"{LATEST_HOUR:02d}:00"):
        raise NotConfident(f"unusual hours {start}-{end} from {text!r}")
    return {"start": start, "end": end}


def expand_days(text):
    """"Mon-Fri" -> [mon..fri]; "Tue & Thu" -> [tue, thu]; "Mon, Wed, Fri" -> [...]."""
    days = []
    for piece in re.split(LIST_SEPARATOR, text.lower()):
        if "-" in piece:
            first, last = [p.strip() for p in piece.split("-")]
            i, j = DAY_NAMES.index(first), DAY_NAMES.index(last)
            if j < i:
                raise NotConfident(f"backwards day range {piece!r}")
            days.extend(DAY_NAMES[i:j + 1])
        else:
            days.append(piece.strip())
    return days


def parse_ordinals(text):
    """"1st & 3rd" -> [1, 3]; "last" -> ["last"]."""
    weeks = []
    for piece in re.split(LIST_SEPARATOR, text.lower()):
        weeks.append("last" if piece == "last" else int(piece[0]))
    return weeks


# ---------- parsing one segment, e.g. "Tue & Thu 9-11:30am, 1:30-3:30pm" ----------

def parse_segment(segment, notes):
    """Return (rule, appointment_available) for one ';'-separated piece."""
    text = segment.strip()

    day_match = DAY_SPEC.match(text)
    if not day_match:
        raise NotConfident(f"doesn't start with days: {text!r}")

    rule = {"days": expand_days(day_match.group("days"))}
    if day_match.group("ordinals"):
        rule["weeks"] = parse_ordinals(day_match.group("ordinals"))
    rest = text[day_match.end():].strip()

    appointment_available = False
    # Check "no appointment" BEFORE "appointment", or it would read as needing one!
    if re.search(r"\bno appointment\b", rest, re.IGNORECASE):
        rest = re.sub(r",?\s*\bno appointment\b", "", rest, flags=re.IGNORECASE)
    if re.search(r"\bor appointment\b", rest, re.IGNORECASE):
        appointment_available = True
        rest = re.sub(r"\s*\bor appointment\b", "", rest, flags=re.IGNORECASE)

    # Parentheses: "(appointment)" is understood; "(drive-through)" is a note;
    # anything else, like "(closed 1-1:30)", is too tricky: flag it.
    for inside in re.findall(r"\(([^)]*)\)", rest):
        if inside.strip().lower() == "appointment":
            rule["appointment"] = True
        elif inside.strip().lower() in NOTE_WORDS:
            notes.append(inside.strip())
        else:
            raise NotConfident(f"unexpected note in parentheses: ({inside})")
    rest = re.sub(r"\([^)]*\)", "", rest)

    # Trailing words like "curbside" are notes.
    for word in NOTE_WORDS:
        if re.search(rf"\b{word}\b", rest, re.IGNORECASE):
            notes.append(word)
            rest = re.sub(rf"\s*\b{word}\b", "", rest, flags=re.IGNORECASE)

    windows = []
    for piece in rest.split(","):
        piece = piece.strip().lower()
        if not piece:
            continue
        if piece in ("appointment", "appointment only"):
            rule["appointment"] = True
        elif TIME_RANGE.match(piece):
            windows.append(parse_time_range(piece))
        else:
            raise NotConfident(f"don't understand {piece!r} in {text!r}")

    if not windows:
        raise NotConfident(f"no times found in {text!r}")
    rule["windows"] = windows
    return rule, appointment_available


# ---------- parsing a whole hours_text ----------

def parse_hours(hours_text):
    """Return (schedule, notes). Raises NotConfident if unsure."""
    text = (hours_text or "").strip()
    lowered = text.lower()
    notes = []

    if not text:
        raise NotConfident("hours are blank")
    if re.fullmatch(r"call( ahead)? for hours", lowered):
        return {"type": "unknown"}, notes
    if lowered.startswith("24/7"):
        return {"type": "always_open"}, notes
    if re.fullmatch(rf"{DAY}(-{DAY})? by appointment", lowered):
        return {"type": "appointment_only"}, notes

    rules = []
    appointment_available = False
    for segment in text.split(";"):
        segment = segment.strip()
        if VISIT_LIMIT.search(segment):
            notes.append(segment)  # "5 visits/yr" is a rule for visitors, not hours
            continue
        rule, also_by_appointment = parse_segment(segment, notes)
        rules.append(rule)
        appointment_available = appointment_available or also_by_appointment

    schedule = {"type": "scheduled", "rules": rules}
    if appointment_available:
        schedule["appointment_available"] = True
    try:
        validate_schedule(schedule)
    except ValueError as error:
        raise NotConfident(str(error))
    return schedule, notes


# ---------- the rest of the CSV columns ----------

def yes_no(value):
    """"yes" -> True, "no" -> False, blank -> None (we don't know)."""
    value = (value or "").strip().lower()
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def number_or_none(value):
    value = (value or "").strip()
    return float(value) if value else None


def text_or_none(value):
    value = (value or "").strip()
    return value or None


def make_id(name):
    """"Salvation Army Denton" -> "salvation-army-denton"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def convert_row(row, overrides):
    """Turn one CSV row into one pantry dict. Also returns a flag reason or None."""
    name = row["name"].strip()
    flag = None
    notes = []

    if name in overrides:
        schedule = overrides[name]
        validate_schedule(schedule)  # a typo in a hand fix should stop the run
    else:
        try:
            schedule, notes = parse_hours(row["hours_text"])
        except NotConfident as reason:
            schedule = {"type": "unknown"}
            flag = str(reason)

    pantry = {
        "id": make_id(name),
        "name": name,
        "address": text_or_none(row["address"]),
        "city": text_or_none(row["city"]),
        "zip": text_or_none(row["zip"]),
        "lat": number_or_none(row["lat"]),
        "lng": number_or_none(row["lng"]),
        "hours_text": row["hours_text"].strip(),
        "schedule": schedule,
        "notes": notes,
        "needs_review": flag is not None,
        "id_required": yes_no(row["id_required"]),
        "drive_thru": yes_no(row["drive_thru"]),
        "spanish": yes_no(row["spanish"]),
        "serves": text_or_none(row["serves_zips"]),
        "phone": text_or_none(row["phone"]),
        "website": text_or_none(row["website"]),
        "date_verified": text_or_none(row["date_verified"]),
    }
    return pantry, flag


def load_overrides():
    """Hand-written schedules, keyed by pantry name. Missing file = no overrides."""
    if not OVERRIDES_PATH.exists():
        return {}
    with open(OVERRIDES_PATH, encoding="utf-8") as f:
        return json.load(f)


def main():
    overrides = load_overrides()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pantries, flagged = [], []
    for row in rows:
        pantry, flag = convert_row(row, overrides)
        pantries.append(pantry)
        if flag:
            flagged.append((pantry["name"], pantry["hours_text"], flag))

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(pantries, f, indent=2, ensure_ascii=False)
        f.write("\n")

    call_for_hours = [p["name"] for p in pantries
                      if p["schedule"]["type"] == "unknown" and not p["needs_review"]]
    no_location = [p["name"] for p in pantries if p["lat"] is None or p["lng"] is None]
    used_overrides = sum(1 for p in pantries if p["name"] in overrides)

    print(f"Wrote {len(pantries)} pantries to {JSON_PATH.relative_to(PROJECT_DIR)}")
    print(f"  parsed automatically: {len(pantries) - len(flagged) - len(call_for_hours) - used_overrides}")
    print(f"  from schedule_overrides.json: {used_overrides}")
    print(f"  'call for hours' (no hours listed): {len(call_for_hours)}")
    print(f"  FLAGGED for hand-fixing: {len(flagged)}")

    if flagged:
        print("\nFLAGGED: add a schedule for each to data/schedule_overrides.json")
        for i, (name, hours_text, reason) in enumerate(flagged, 1):
            print(f"\n{i:2}. {name}")
            print(f"    hours_text: {hours_text}")
            print(f"    why:        {reason}")

    if no_location:
        print(f"\nFYI: {len(no_location)} pantries have no lat/lng and won't appear on the map:")
        for name in no_location:
            print(f"    - {name}")


if __name__ == "__main__":
    main()
