"""Tests for backend/forecast.py and POST /forecast.

Most tests use cases where the right answer can be worked out by hand.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.forecast import forecast, history_weight, simulate_future_hours

client = TestClient(main.app)


def run(**kwargs):
    kwargs.setdefault("seed", 42)
    return forecast(**kwargs)


# ---------- answers you can check by hand ----------

def test_already_above_target_is_100_percent():
    result = run(logged_hours_this_month=85, past_weekly_totals=[], days_left=10)
    assert result["probability"] == 1.0
    assert result["hours_needed"] == 0


def test_no_history_zero_hours_two_days_left_is_near_0_percent():
    # 2 days = 2/7 of a week. To reach 80 you'd need a 280-hour default week
    # (mean 12, sd 6): that's 44 standard deviations away. Impossible.
    result = run(logged_hours_this_month=0, past_weekly_totals=[], days_left=2)
    assert result["probability"] < 0.001


def test_no_days_left_just_compares_logged_hours():
    assert run(logged_hours_this_month=80, past_weekly_totals=[20, 20, 20], days_left=0)["probability"] == 1.0
    assert run(logged_hours_this_month=79.5, past_weekly_totals=[20, 20, 20], days_left=0)["probability"] == 0.0


def test_perfectly_steady_20_hour_weeks_reach_exactly_80():
    # 4 weeks x 20 h = 80, every single simulation
    result = run(logged_hours_this_month=0, past_weekly_totals=[20, 20, 20], days_left=28)
    assert result["probability"] == 1.0
    assert result["percentiles"] == {"p10": 80.0, "p50": 80.0, "p90": 80.0}


def test_perfectly_steady_10_hour_weeks_never_reach_80():
    result = run(logged_hours_this_month=0, past_weekly_totals=[10, 10, 10], days_left=28)
    assert result["probability"] == 0.0
    assert result["percentiles"]["p50"] == 40.0


# ---------- partial weeks ----------

def test_partial_week_counts_for_its_fraction():
    # 1 hour a day = 7-hour weeks. 10 days left = 1 week + 3/7 week = 10 hours.
    rng = np.random.default_rng(0)
    future = simulate_future_hours([7, 7, 7], days_left=10, simulations=100, rng=rng)
    assert np.allclose(future, 10.0)


def test_partial_week_edge_right_at_target():
    history = [7, 7, 7]  # 10 more hours in 10 days
    assert run(logged_hours_this_month=70, past_weekly_totals=history, days_left=10)["probability"] == 1.0
    assert run(logged_hours_this_month=69.9, past_weekly_totals=history, days_left=10)["probability"] == 0.0


# ---------- blending with the default week ----------

@pytest.mark.parametrize("weeks, weight", [(0, 0.0), (1, 1 / 3), (2, 2 / 3), (3, 1.0), (10, 1.0)])
def test_history_weight(weeks, weight):
    assert history_weight(weeks) == pytest.approx(weight)


def test_one_week_of_history_is_used_about_one_third_of_the_time():
    # One 50-hour past week; 7 days left; need 40. Only a draw from HISTORY (50 h)
    # can get there: the default week (mean 12, sd 6) almost never hits 40.
    # History is used 1/3 of the time, so the answer should be about 33%.
    result = run(logged_hours_this_month=0, past_weekly_totals=[50], days_left=7, target=40)
    assert result["probability"] == pytest.approx(1 / 3, abs=0.02)


def test_default_week_is_never_negative():
    rng = np.random.default_rng(1)
    future = simulate_future_hours([], days_left=28, simulations=10_000, rng=rng)
    assert future.min() >= 0


def test_three_weeks_of_history_ignores_default():
    # With 3+ weeks, every draw comes from history, so only 0 or 30 are possible.
    rng = np.random.default_rng(2)
    future = simulate_future_hours([0, 0, 30], days_left=7, simulations=5_000, rng=rng)
    assert set(np.unique(future)) <= {0.0, 30.0}


# ---------- percentiles and general sanity ----------

def test_percentiles_are_in_order_and_at_least_logged_hours():
    result = run(logged_hours_this_month=30, past_weekly_totals=[5, 15, 25, 12], days_left=17)
    p = result["percentiles"]
    assert 30 <= p["p10"] <= p["p50"] <= p["p90"]


def test_more_history_hours_means_higher_chance():
    low = run(logged_hours_this_month=40, past_weekly_totals=[8, 12, 16], days_left=14)
    high = run(logged_hours_this_month=40, past_weekly_totals=[18, 22, 26], days_left=14)
    assert low["probability"] < high["probability"]


def test_same_seed_same_answer():
    args = dict(logged_hours_this_month=30, past_weekly_totals=[10, 20, 15], days_left=15, seed=7)
    assert forecast(**args) == forecast(**args)


def test_uses_10000_simulations_by_default():
    assert run(logged_hours_this_month=0, past_weekly_totals=[], days_left=7)["simulations"] == 10_000


# ---------- what-if ----------

def test_no_what_if_unless_asked():
    assert run(logged_hours_this_month=10, past_weekly_totals=[20], days_left=7)["what_if"] is None


def test_what_if_extra_hours_can_push_over_target():
    # Steady 20-hour weeks, 3 weeks left: 15 + 60 = 75 (miss). With 10 extra: 85 (hit).
    result = run(logged_hours_this_month=15, past_weekly_totals=[20, 20, 20], days_left=21,
                 what_if_extra_hours=10)
    assert result["probability"] == 0.0
    assert result["what_if"]["probability"] == 1.0
    assert result["what_if"]["percentiles"]["p50"] == 85.0


def test_what_if_never_lowers_the_chance():
    result = run(logged_hours_this_month=40, past_weekly_totals=[5, 15, 25], days_left=14,
                 what_if_extra_hours=4)
    assert result["what_if"]["probability"] >= result["probability"]


# ---------- bad input ----------

@pytest.mark.parametrize("kwargs", [
    dict(logged_hours_this_month=-1, past_weekly_totals=[], days_left=5),
    dict(logged_hours_this_month=0, past_weekly_totals=[-3], days_left=5),
    dict(logged_hours_this_month=0, past_weekly_totals=[], days_left=-1),
    dict(logged_hours_this_month=0, past_weekly_totals=[], days_left=5, target=0),
    dict(logged_hours_this_month=0, past_weekly_totals=[], days_left=5, what_if_extra_hours=-2),
])
def test_bad_input_raises(kwargs):
    with pytest.raises(ValueError):
        forecast(**kwargs)


# ---------- the API endpoint ----------

def test_forecast_endpoint():
    response = client.post("/forecast", json={
        "logged_hours_this_month": 85, "past_weekly_totals": [], "days_left": 10,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["probability"] == 1.0
    assert body["target"] == 80  # default


def test_forecast_endpoint_what_if():
    body = client.post("/forecast", json={
        "logged_hours_this_month": 15, "past_weekly_totals": [20, 20, 20], "days_left": 21,
        "what_if_extra_hours": 10,
    }).json()
    assert body["what_if"]["probability"] == 1.0


@pytest.mark.parametrize("payload", [
    {"logged_hours_this_month": -5, "days_left": 10},
    {"logged_hours_this_month": 10, "days_left": 40},
    {"logged_hours_this_month": 10, "days_left": 10, "past_weekly_totals": [200]},
    {"logged_hours_this_month": 10},  # days_left missing
])
def test_forecast_endpoint_rejects_bad_input(payload):
    assert client.post("/forecast", json=payload).status_code == 422
