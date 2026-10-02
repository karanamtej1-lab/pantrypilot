"""Tests for backend/hours.py.

Calendar facts these tests rely on (check with `python -m calendar 2026`):
  Aug 2026 Saturdays: 1, 8, 15, 22, 29   <- 5 Saturdays; the 29th is the 5th AND last
  Sep 2026 Saturdays: 5, 12, 19, 26      <- 4 Saturdays; the 26th is the 4th AND last
  Oct 2026 Saturdays: 3, 10, 17, 24, 31
  Nov 2026 Saturdays: 7, 14, 21, 28
  Dec 2026 Saturdays: 5, 12, 19, 26      <- next Saturday is Jan 2, 2027
  Feb 2026 Saturdays: 7, 14, 21, 28      <- next Saturday is Mar 7
  Sep 2026: Mon 7/14/21/28, Tue 1/8/15/22/29, Wed 2/9/16/23/30, Thu 3/10/17/24
"""

from datetime import date, datetime, timezone

import pytest

from backend.hours import (
    APPOINTMENT,
    CLOSED,
    LATER_TODAY,
    OPEN,
    UNKNOWN,
    is_last_weekday_of_month,
    is_open_now,
    nth_weekday_of_month,
    status,
    validate_schedule,
)


def at(year, month, day, hour, minute=0):
    """A North Texas local time (no timezone attached = America/Chicago)."""
    return datetime(year, month, day, hour, minute)


# ---------- schedules copied from real rows in data/pantries.csv ----------

# NTX Community Food Pantry: "Mon 9am-12pm; Wed 9am-2pm; Thu 4:30-6:30pm"
NTX = {"type": "scheduled", "rules": [
    {"days": ["mon"], "windows": [{"start": "09:00", "end": "12:00"}]},
    {"days": ["wed"], "windows": [{"start": "09:00", "end": "14:00"}]},
    {"days": ["thu"], "windows": [{"start": "16:30", "end": "18:30"}]},
]}

# Salvation Army Lewisville: "Tue & Thu 9-11:30am, 1:30-3:30pm"
LUNCH_BREAK = {"type": "scheduled", "rules": [
    {"days": ["tue", "thu"], "windows": [
        {"start": "09:00", "end": "11:30"},
        {"start": "13:30", "end": "15:30"},
    ]},
]}

# Heart of the City Carrollton: "2nd & 4th Sat 9-11am"
SECOND_FOURTH_SAT = {"type": "scheduled", "rules": [
    {"days": ["sat"], "weeks": [2, 4], "windows": [{"start": "09:00", "end": "11:00"}]},
]}

# Heart of the City Frisco: "1st & 3rd Sat 9-11am"
FIRST_THIRD_SAT = {"type": "scheduled", "rules": [
    {"days": ["sat"], "weeks": [1, 3], "windows": [{"start": "09:00", "end": "11:00"}]},
]}

# Made-up example for "last Saturday of the month"
LAST_SAT = {"type": "scheduled", "rules": [
    {"days": ["sat"], "weeks": ["last"], "windows": [{"start": "09:00", "end": "11:00"}]},
]}

# Minnie's Food Pantry: "Wed-Sat 8:30-11:30am; closed 5th Sat"
MINNIES = {"type": "scheduled", "rules": [
    {"days": ["wed", "thu", "fri"], "windows": [{"start": "08:30", "end": "11:30"}]},
    {"days": ["sat"], "weeks": [1, 2, 3, 4], "windows": [{"start": "08:30", "end": "11:30"}]},
]}

# Asbury Relief Ministry: "1st/3rd Mon 6-7:30pm; 2nd/4th Mon 10am-12pm"
ASBURY = {"type": "scheduled", "rules": [
    {"days": ["mon"], "weeks": [1, 3], "windows": [{"start": "18:00", "end": "19:30"}]},
    {"days": ["mon"], "weeks": [2, 4], "windows": [{"start": "10:00", "end": "12:00"}]},
]}

# Westside Baptist: "Jan-Oct 4th Sat, Nov-Dec 2nd Sat, 8am-12pm"
WESTSIDE = {"type": "scheduled", "rules": [
    {"days": ["sat"], "weeks": [4], "months": list(range(1, 11)),
     "windows": [{"start": "08:00", "end": "12:00"}]},
    {"days": ["sat"], "weeks": [2], "months": [11, 12],
     "windows": [{"start": "08:00", "end": "12:00"}]},
]}

# Heart of the City Mill St: "Tue 2-6pm; Thu 10am-1pm; Sat 9-11am (appointment)"
MILL_ST = {"type": "scheduled", "rules": [
    {"days": ["tue"], "windows": [{"start": "14:00", "end": "18:00"}]},
    {"days": ["thu"], "windows": [{"start": "10:00", "end": "13:00"}]},
    {"days": ["sat"], "windows": [{"start": "09:00", "end": "11:00"}], "appointment": True},
]}

# Denton Wesley Foundation: "Thu 11am-2pm or appointment"
WESLEY = {"type": "scheduled", "appointment_available": True, "rules": [
    {"days": ["thu"], "windows": [{"start": "11:00", "end": "14:00"}]},
]}

APPOINTMENT_ONLY = {"type": "appointment_only"}  # CCA: "Mon-Fri by appointment"
ALWAYS_OPEN = {"type": "always_open"}            # Little Free Pantry: "24/7"
CALL_FOR_HOURS = {"type": "unknown"}             # "Call for hours"

ALL_REAL_SCHEDULES = [NTX, LUNCH_BREAK, SECOND_FOURTH_SAT, FIRST_THIRD_SAT, LAST_SAT,
                      MINNIES, ASBURY, WESTSIDE, MILL_ST, WESLEY,
                      APPOINTMENT_ONLY, ALWAYS_OPEN, CALL_FOR_HOURS]


# ---------- weekly schedules ----------

def test_open_during_weekly_hours():
    assert status(NTX, at(2026, 9, 28, 10)) == OPEN  # Mon 10am


def test_closed_on_a_day_with_no_hours():
    assert status(NTX, at(2026, 9, 29, 10)) == CLOSED  # Tue


def test_each_day_uses_its_own_hours():
    assert status(NTX, at(2026, 9, 30, 13)) == OPEN        # Wed 1pm (Wed runs to 2pm)
    assert status(NTX, at(2026, 9, 28, 13)) == CLOSED      # Mon 1pm (Mon ended at noon)
    assert status(NTX, at(2026, 10, 1, 13)) == LATER_TODAY  # Thu 1pm (opens 4:30pm)


# ---------- exactly at opening / closing ----------

def test_open_at_exact_opening_minute():
    assert status(NTX, at(2026, 9, 28, 9, 0)) == OPEN


def test_one_minute_before_opening_is_later_today():
    assert status(NTX, at(2026, 9, 28, 8, 59)) == LATER_TODAY


def test_one_minute_before_closing_is_open():
    assert status(NTX, at(2026, 9, 28, 11, 59)) == OPEN


def test_closed_at_exact_closing_minute():
    assert status(NTX, at(2026, 9, 28, 12, 0)) == CLOSED


def test_one_second_before_closing_is_open():
    assert status(NTX, datetime(2026, 9, 28, 11, 59, 59)) == OPEN


def test_half_hour_times():
    assert status(NTX, at(2026, 10, 1, 16, 29)) == LATER_TODAY  # Thu 4:29pm
    assert status(NTX, at(2026, 10, 1, 16, 30)) == OPEN         # Thu 4:30pm
    assert status(NTX, at(2026, 10, 1, 18, 30)) == CLOSED       # Thu 6:30pm


def test_midnight_is_later_today_if_hours_that_day():
    assert status(NTX, at(2026, 9, 28, 0, 0)) == LATER_TODAY  # Mon 12:00am


# ---------- multiple windows in one day ----------

def test_open_in_morning_window():
    assert status(LUNCH_BREAK, at(2026, 9, 29, 10)) == OPEN  # Tue


def test_lunch_gap_is_later_today():
    assert status(LUNCH_BREAK, at(2026, 9, 29, 12)) == LATER_TODAY


def test_open_in_afternoon_window():
    assert status(LUNCH_BREAK, at(2026, 9, 29, 13, 30)) == OPEN


def test_closed_after_last_window():
    assert status(LUNCH_BREAK, at(2026, 9, 29, 15, 30)) == CLOSED


# ---------- nth weekday of the month ----------

@pytest.mark.parametrize("day, expected", [
    (1, 1), (7, 1),    # days 1-7   -> 1st
    (8, 2), (14, 2),   # days 8-14  -> 2nd
    (15, 3), (21, 3),  # days 15-21 -> 3rd
    (22, 4), (28, 4),  # days 22-28 -> 4th
    (29, 5), (31, 5),  # days 29-31 -> 5th
])
def test_nth_weekday_of_month(day, expected):
    assert nth_weekday_of_month(date(2026, 8, day)) == expected


def test_second_and_fourth_saturday_open():
    assert status(SECOND_FOURTH_SAT, at(2026, 9, 12, 10)) == OPEN  # 2nd Sat
    assert status(SECOND_FOURTH_SAT, at(2026, 9, 26, 10)) == OPEN  # 4th Sat


def test_first_and_third_saturday_closed_for_2nd_4th_pantry():
    assert status(SECOND_FOURTH_SAT, at(2026, 9, 5, 10)) == CLOSED   # 1st Sat
    assert status(SECOND_FOURTH_SAT, at(2026, 9, 19, 10)) == CLOSED  # 3rd Sat


def test_fifth_saturday_closed_for_2nd_4th_pantry():
    assert status(SECOND_FOURTH_SAT, at(2026, 8, 29, 10)) == CLOSED  # 5th Sat


def test_fifth_saturday_closed_for_1st_3rd_pantry():
    assert status(FIRST_THIRD_SAT, at(2026, 8, 29, 10)) == CLOSED
    assert status(FIRST_THIRD_SAT, at(2026, 8, 1, 10)) == OPEN  # 1st Sat, same month


def test_nth_rule_ignores_other_weekdays_in_same_week():
    # Sep 10 is the 2nd Thursday, but the rule is for Saturdays only.
    assert status(SECOND_FOURTH_SAT, at(2026, 9, 10, 10)) == CLOSED


# ---------- "last" weekday of the month ----------

def test_last_saturday_in_a_month_with_five_saturdays():
    assert status(LAST_SAT, at(2026, 8, 29, 10)) == OPEN    # 5th = last
    assert status(LAST_SAT, at(2026, 8, 22, 10)) == CLOSED  # 4th, but not last


def test_last_saturday_in_a_month_with_four_saturdays():
    assert status(LAST_SAT, at(2026, 9, 26, 10)) == OPEN  # 4th = last


def test_last_saturday_across_year_end():
    assert is_last_weekday_of_month(date(2026, 12, 26)) is True   # next Sat is Jan 2
    assert is_last_weekday_of_month(date(2026, 12, 19)) is False


def test_last_saturday_in_february():
    assert is_last_weekday_of_month(date(2026, 2, 28)) is True  # next Sat is Mar 7
    assert is_last_weekday_of_month(date(2026, 2, 21)) is False


def test_week_4_and_last_can_be_the_same_day():
    assert nth_weekday_of_month(date(2026, 9, 26)) == 4
    assert is_last_weekday_of_month(date(2026, 9, 26)) is True


# ---------- "closed 5th Sat" (Minnie's) ----------

def test_minnies_closed_on_fifth_saturday():
    assert status(MINNIES, at(2026, 8, 29, 9)) == CLOSED


def test_minnies_open_on_fourth_saturday():
    assert status(MINNIES, at(2026, 8, 22, 9)) == OPEN


def test_minnies_open_on_fifth_wednesday():
    # "closed 5th Sat" should not close the 5th Wednesday (Sep 30).
    assert status(MINNIES, at(2026, 9, 30, 9)) == OPEN


# ---------- same day, different hours by week (Asbury) ----------

def test_asbury_first_monday_evening_only():
    assert status(ASBURY, at(2026, 9, 7, 11)) == LATER_TODAY  # 1st Mon, morning
    assert status(ASBURY, at(2026, 9, 7, 18)) == OPEN         # 1st Mon, evening


def test_asbury_second_monday_morning_only():
    assert status(ASBURY, at(2026, 9, 14, 11)) == OPEN    # 2nd Mon, morning
    assert status(ASBURY, at(2026, 9, 14, 18)) == CLOSED  # 2nd Mon, evening


def test_asbury_closed_on_fifth_monday():
    assert status(ASBURY, at(2026, 8, 31, 11)) == CLOSED  # Aug 31 = 5th Mon


# ---------- months (Westside Baptist) ----------

def test_westside_october_uses_4th_saturday():
    assert status(WESTSIDE, at(2026, 10, 24, 9)) == OPEN    # 4th Sat of Oct
    assert status(WESTSIDE, at(2026, 10, 10, 9)) == CLOSED  # 2nd Sat of Oct


def test_westside_november_uses_2nd_saturday():
    assert status(WESTSIDE, at(2026, 11, 14, 9)) == OPEN    # 2nd Sat of Nov
    assert status(WESTSIDE, at(2026, 11, 28, 9)) == CLOSED  # 4th Sat of Nov


# ---------- appointments ----------

def test_appointment_only_pantry():
    assert status(APPOINTMENT_ONLY, at(2026, 9, 28, 10)) == APPOINTMENT
    assert is_open_now(APPOINTMENT_ONLY, at(2026, 9, 28, 10)) is False


def test_appointment_window_is_not_walk_in_open():
    saturday = at(2026, 10, 3, 10)
    assert status(MILL_ST, saturday) == APPOINTMENT
    assert is_open_now(MILL_ST, saturday) is False


def test_walk_in_days_still_open_at_mixed_pantry():
    assert status(MILL_ST, at(2026, 9, 29, 15)) == OPEN  # Tue 3pm


def test_appointment_window_later_today():
    assert status(MILL_ST, at(2026, 10, 3, 8)) == LATER_TODAY


def test_or_appointment_open_during_hours():
    assert status(WESLEY, at(2026, 10, 1, 12)) == OPEN  # Thu noon


def test_or_appointment_before_hours_is_later_today():
    assert status(WESLEY, at(2026, 10, 1, 9)) == LATER_TODAY


def test_or_appointment_outside_hours_is_appointment():
    assert status(WESLEY, at(2026, 9, 28, 12)) == APPOINTMENT  # Mon


# ---------- other schedule types ----------

def test_always_open():
    assert status(ALWAYS_OPEN, at(2026, 9, 27, 3)) == OPEN  # Sun 3am
    assert is_open_now(ALWAYS_OPEN, at(2026, 9, 27, 3)) is True


def test_call_for_hours_is_unknown_not_closed():
    assert status(CALL_FOR_HOURS, at(2026, 9, 28, 10)) == UNKNOWN
    assert is_open_now(CALL_FOR_HOURS, at(2026, 9, 28, 10)) is False


# ---------- is_open_now ----------

def test_is_open_now_true_only_when_status_is_open():
    assert is_open_now(NTX, at(2026, 9, 28, 10)) is True        # open
    assert is_open_now(NTX, at(2026, 9, 28, 8)) is False        # later_today
    assert is_open_now(NTX, at(2026, 9, 28, 12)) is False       # closed


def test_no_time_given_uses_now():
    assert status(ALWAYS_OPEN) == OPEN
    assert is_open_now(CALL_FOR_HOURS) is False


# ---------- timezones ----------

def test_utc_time_is_converted_during_daylight_time():
    # 3:00pm UTC on Mon Sep 28 = 10:00am in Texas (CDT, UTC-5)
    utc = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)
    assert status(NTX, utc) == OPEN


def test_utc_time_is_converted_during_standard_time():
    # Mon Jan 4 2027: 3:00pm UTC = 9:00am in Texas (CST, UTC-6), opening minute
    assert status(NTX, datetime(2027, 1, 4, 15, 0, tzinfo=timezone.utc)) == OPEN
    # 2:59pm UTC = 8:59am in Texas, one minute early
    assert status(NTX, datetime(2027, 1, 4, 14, 59, tzinfo=timezone.utc)) == LATER_TODAY


def test_utc_date_can_differ_from_texas_date():
    # 1:00am UTC Tuesday = 8:00pm Monday in Texas -> Monday's hours are over
    utc = datetime(2026, 9, 29, 1, 0, tzinfo=timezone.utc)
    assert status(NTX, utc) == CLOSED


# ---------- validate_schedule ----------

@pytest.mark.parametrize("schedule", ALL_REAL_SCHEDULES)
def test_real_examples_are_valid(schedule):
    validate_schedule(schedule)  # should not raise


@pytest.mark.parametrize("bad_schedule", [
    {"type": "sometimes"},
    {"type": "scheduled", "rules": []},
    {"type": "scheduled", "rules": [{"days": ["Tues"], "windows": [{"start": "09:00", "end": "10:00"}]}]},
    {"type": "scheduled", "rules": [{"days": [], "windows": [{"start": "09:00", "end": "10:00"}]}]},
    {"type": "scheduled", "rules": [{"days": ["sat"], "weeks": [6], "windows": [{"start": "09:00", "end": "10:00"}]}]},
    {"type": "scheduled", "rules": [{"days": ["sat"], "months": [13], "windows": [{"start": "09:00", "end": "10:00"}]}]},
    {"type": "scheduled", "rules": [{"days": ["sat"], "windows": []}]},
    {"type": "scheduled", "rules": [{"days": ["sat"], "windows": [{"start": "12:00", "end": "09:00"}]}]},
    {"type": "scheduled", "rules": [{"days": ["sat"], "windows": [{"start": "09:00", "end": "09:00"}]}]},
])
def test_bad_schedules_are_rejected(bad_schedule):
    with pytest.raises(ValueError):
        validate_schedule(bad_schedule)
