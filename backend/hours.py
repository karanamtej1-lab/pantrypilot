"""Opening-hours logic for PantryPilot.

A pantry's schedule is a dict in the format described in data/SCHEDULE_FORMAT.md.
All times are local North Texas time (America/Chicago).
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Chicago")

# Same order as Python's date.weekday(): Monday is 0, Sunday is 6.
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

SCHEDULE_TYPES = {"scheduled", "appointment_only", "always_open", "unknown"}

OPEN = "open"
LATER_TODAY = "later_today"
CLOSED = "closed"
APPOINTMENT = "appointment"
UNKNOWN = "unknown"


def to_local(when=None):
    """Return `when` as a North Texas time. No `when` means right now.

    A datetime without a timezone is assumed to already be North Texas time.
    """
    if when is None:
        return datetime.now(TIMEZONE)
    if when.tzinfo is None:
        return when.replace(tzinfo=TIMEZONE)
    return when.astimezone(TIMEZONE)


def parse_time(text):
    """Turn "13:30" into time(13, 30)."""
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


# ---------- nth-weekday-of-the-month logic ----------

def nth_weekday_of_month(day):
    """Which occurrence of its weekday this date is: 1st, 2nd, ... 5th.

    Days 1-7 are always the 1st of their weekday, days 8-14 the 2nd, and so on.
    """
    return (day.day - 1) // 7 + 1


def is_last_weekday_of_month(day):
    """True if the same weekday next week falls in a different month."""
    one_week_later = day + timedelta(days=7)
    return one_week_later.month != day.month


def week_matches(weeks, day):
    """Does `day` fit the rule's `weeks` list (e.g. [2, 4] or ["last"])?"""
    if not weeks:
        return True  # no `weeks` means every week
    if nth_weekday_of_month(day) in weeks:
        return True
    if "last" in weeks and is_last_weekday_of_month(day):
        return True
    return False


# ---------- matching rules to dates ----------

def rule_applies_on(rule, day):
    """True if this rule has hours on this date."""
    if DAY_NAMES[day.weekday()] not in rule["days"]:
        return False
    months = rule.get("months")
    if months and day.month not in months:
        return False
    return week_matches(rule.get("weeks"), day)


def windows_on(schedule, day):
    """Every (start, end, needs_appointment) window on this date."""
    windows = []
    for rule in schedule.get("rules", []):
        if rule_applies_on(rule, day):
            for window in rule["windows"]:
                windows.append((
                    parse_time(window["start"]),
                    parse_time(window["end"]),
                    rule.get("appointment", False),
                ))
    return windows


# ---------- the two public functions ----------

def status(schedule, when=None):
    """One of "open", "later_today", "closed", "appointment", or "unknown"."""
    kind = schedule.get("type", "scheduled")
    if kind == "always_open":
        return OPEN
    if kind == "appointment_only":
        return APPOINTMENT
    if kind == "unknown":
        return UNKNOWN

    now = to_local(when)
    current = now.time()
    in_appointment_window = False
    has_later_window = False

    for start, end, needs_appointment in windows_on(schedule, now.date()):
        if start <= current < end:  # open at `start`, closed at exactly `end`
            if not needs_appointment:
                return OPEN
            in_appointment_window = True
        elif current < start:
            has_later_window = True

    if in_appointment_window:
        return APPOINTMENT
    if has_later_window:
        return LATER_TODAY
    if schedule.get("appointment_available"):
        return APPOINTMENT
    return CLOSED


def is_open_now(schedule, when=None):
    """True only if someone could walk in right now (used by the "Open now" filter)."""
    return status(schedule, when) == OPEN


# ---------- catching typos in the data ----------

def validate_schedule(schedule):
    """Raise ValueError if a schedule is malformed.

    A typo like "Tues" would otherwise make a pantry silently look closed.
    """
    kind = schedule.get("type", "scheduled")
    if kind not in SCHEDULE_TYPES:
        raise ValueError(f"unknown type: {kind!r}")
    if kind != "scheduled":
        return
    if not schedule.get("rules"):
        raise ValueError("a scheduled pantry needs at least one rule")

    for rule in schedule["rules"]:
        if not rule.get("days"):
            raise ValueError("rule has no days")
        for day_name in rule["days"]:
            if day_name not in DAY_NAMES:
                raise ValueError(f"bad day: {day_name!r} (use mon, tue, ...)")
        for week in rule.get("weeks") or []:
            if week != "last" and week not in (1, 2, 3, 4, 5):
                raise ValueError(f"bad week: {week!r} (use 1-5 or 'last')")
        for month in rule.get("months") or []:
            if month not in range(1, 13):
                raise ValueError(f"bad month: {month!r}")
        if not rule.get("windows"):
            raise ValueError("rule has no time windows")
        for window in rule["windows"]:
            if parse_time(window["start"]) >= parse_time(window["end"]):
                raise ValueError(f"window ends before it starts: {window}")


# ---------- readable text (used by the AI assistant) ----------

DAY_LABELS = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}
WEEK_LABELS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", "last": "last"}
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _time_text(hhmm):
    """"16:30" -> "4:30 PM"."""
    t = parse_time(hhmm)
    hour = t.hour % 12 or 12
    suffix = "PM" if t.hour >= 12 else "AM"
    return f"{hour}:{t.minute:02d} {suffix}" if t.minute else f"{hour} {suffix}"


def _days_text(days):
    ordered = sorted(days, key=DAY_NAMES.index)
    indexes = [DAY_NAMES.index(d) for d in ordered]
    if len(ordered) >= 3 and indexes == list(range(indexes[0], indexes[-1] + 1)):
        return f"{DAY_LABELS[ordered[0]]}-{DAY_LABELS[ordered[-1]]}"
    return " & ".join(DAY_LABELS[d] for d in ordered)


def describe_schedule(schedule):
    """A schedule as short readable lines, e.g. ["2nd & 4th Sat 9 AM-11 AM"]."""
    kind = schedule.get("type", "scheduled")
    if kind == "always_open":
        return ["Open 24 hours, every day"]
    if kind == "appointment_only":
        return ["By appointment only"]
    if kind == "unknown":
        return ["Hours not confirmed; call first"]

    lines = []
    for rule in schedule["rules"]:
        when = _days_text(rule["days"])
        if rule.get("weeks"):
            when = " & ".join(WEEK_LABELS[w] for w in rule["weeks"]) + " " + when
        if rule.get("months"):
            when = ", ".join(MONTH_LABELS[m - 1] for m in rule["months"]) + ": " + when
        times = ", ".join(f"{_time_text(w['start'])}-{_time_text(w['end'])}" for w in rule["windows"])
        lines.append(f"{when} {times}" + (" (appointment needed)" if rule.get("appointment") else ""))
    if schedule.get("appointment_available"):
        lines.append("Other times by appointment")
    return lines
