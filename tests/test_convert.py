"""Tests for the hours_text parser in backend/convert.py."""

import pytest

from backend.convert import NotConfident, parse_hours, parse_time_range


# ---------- time ranges ----------

@pytest.mark.parametrize("text, start, end", [
    ("9am-12pm", "09:00", "12:00"),
    ("9-11am", "09:00", "11:00"),          # start borrows "am" from the end
    ("4:30-6:30pm", "16:30", "18:30"),     # start borrows "pm"
    ("1-3:45pm", "13:00", "15:45"),        # 1pm, not 1am
    ("12-4pm", "12:00", "16:00"),          # 12pm is noon
    ("11-2pm", "11:00", "14:00"),          # 11pm would be after 2pm, so it's 11am
    ("10am-12:15pm", "10:00", "12:15"),
    ("8:30am-4:30pm", "08:30", "16:30"),
])
def test_time_ranges(text, start, end):
    assert parse_time_range(text) == {"start": start, "end": end}


@pytest.mark.parametrize("text", [
    "9-12",        # no am/pm at all: is 12 noon or midnight? Don't guess.
    "5am-7am",     # earlier than any pantry opens: probably a typo
    "9pm-11pm",    # later than any pantry closes
    "2pm-1pm",     # closes before it opens
])
def test_suspicious_time_ranges_are_rejected(text):
    with pytest.raises(NotConfident):
        parse_time_range(text)


# ---------- day lists ----------

def test_day_range():
    schedule, _ = parse_hours("Mon-Thu 1-4pm")
    assert schedule["rules"][0]["days"] == ["mon", "tue", "wed", "thu"]


@pytest.mark.parametrize("text", ["Tue & Thu 9-11am", "Tue/Thu 9-11am", "Tue, Thu 9-11am"])
def test_day_list_separators(text):
    schedule, _ = parse_hours(text)
    assert schedule["rules"][0]["days"] == ["tue", "thu"]


def test_nth_weekday():
    schedule, _ = parse_hours("2nd & 4th Sat 9-11am")
    assert schedule["rules"][0]["weeks"] == [2, 4]


def test_nth_weekday_with_slash():
    schedule, _ = parse_hours("1st/3rd Mon 6-7:30pm; 2nd/4th Mon 10am-12pm")
    assert [r["weeks"] for r in schedule["rules"]] == [[1, 3], [2, 4]]


def test_multiple_windows():
    schedule, _ = parse_hours("Tue & Thu 9-11:30am, 1:30-3:30pm")
    assert schedule["rules"][0]["windows"] == [
        {"start": "09:00", "end": "11:30"},
        {"start": "13:30", "end": "15:30"},
    ]


# ---------- appointments: the trickiest words ----------

def test_no_appointment_does_not_mean_appointment():
    schedule, _ = parse_hours("2nd & 4th Sat 9-11am, no appointment")
    assert "appointment" not in schedule["rules"][0]


def test_appointment_in_parentheses():
    schedule, _ = parse_hours("Sat 9-11am (appointment)")
    assert schedule["rules"][0]["appointment"] is True


def test_appointment_only_after_comma():
    schedule, _ = parse_hours("Tue 9am-12pm, appointment only")
    assert schedule["rules"][0]["appointment"] is True


def test_or_appointment():
    schedule, _ = parse_hours("Thu 11am-2pm or appointment")
    assert schedule["appointment_available"] is True
    assert "appointment" not in schedule["rules"][0]


def test_by_appointment_only():
    schedule, _ = parse_hours("Mon-Fri by appointment")
    assert schedule == {"type": "appointment_only"}


# ---------- special whole-text cases and notes ----------

@pytest.mark.parametrize("text", ["Call for hours", "Call ahead for hours"])
def test_call_for_hours(text):
    assert parse_hours(text)[0] == {"type": "unknown"}


def test_always_open():
    assert parse_hours("24/7 take what you need")[0] == {"type": "always_open"}


def test_visit_limits_become_notes():
    schedule, notes = parse_hours("Mon 9am-4pm; 5 visits/yr")
    assert len(schedule["rules"]) == 1
    assert notes == ["5 visits/yr"]


def test_drive_through_becomes_note():
    _, notes = parse_hours("Wed & Fri 9:30-11:30am (drive-through)")
    assert notes == ["drive-through"]


# ---------- things it must flag, not guess ----------

@pytest.mark.parametrize("text", [
    "Mon-Fri 9am-5pm (Wed to 6pm)",        # exception for one day
    "Tue-Thu 10am-2:45pm (closed 1-1:30)",  # break inside a window
    "Jan-Oct 4th Sat, Nov-Dec 2nd Sat, 8am-12pm",  # month ranges
    "Wed-Sat 8:30-11:30am; closed 5th Sat",
    "1st Sat of month",                    # no times
    "Tue & Thu 9am-3pm; appointment",      # appointment for which hours?
    "Tue 3:30-5pm (schedule online)",      # is an appointment required?
    "",
])
def test_unclear_hours_are_flagged(text):
    with pytest.raises(NotConfident):
        parse_hours(text)
