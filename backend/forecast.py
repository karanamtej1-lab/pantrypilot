"""Hours Coach forecast: chance of reaching 80 hours this month (Monte Carlo).

The idea in one sentence: replay the person's own past weeks at random,
10,000 times, to see how many of those possible futures reach the target.

Steps:
  1. Split the days left into full weeks plus a partial week
     (10 days left = 1 full week + 3/7 of a week).
  2. For every simulation, pick a weekly total for each remaining week by
     drawing at random from the person's past weeks ("bootstrap").
     The partial week counts for its fraction (3/7 of a drawn week).
  3. With fewer than 3 past weeks there isn't enough history to trust, so some
     draws come from a default week instead (mean 12 h, sd 6 h, never below 0).
  4. final hours = hours already logged + simulated future hours.
     probability = share of simulations where final hours >= target.

This is an estimate, not a guarantee and not an official SNAP determination.
"""

import numpy as np

SIMULATIONS = 10_000
DAYS_PER_WEEK = 7

# Default week used when there isn't enough personal history.
DEFAULT_WEEKLY_MEAN = 12.0
DEFAULT_WEEKLY_SD = 6.0
MIN_HISTORY_WEEKS = 3


def history_weight(weeks_of_history):
    """How much to trust personal history: 0 weeks -> 0, 1 -> 1/3, 2 -> 2/3, 3+ -> 1."""
    return min(weeks_of_history / MIN_HISTORY_WEEKS, 1.0)


def sample_weeks(history, shape, rng):
    """Draw random weekly totals: from history (bootstrap) or the default week."""
    default_weeks = np.clip(rng.normal(DEFAULT_WEEKLY_MEAN, DEFAULT_WEEKLY_SD, shape), 0, None)
    if len(history) == 0:
        return default_weeks

    history_weeks = rng.choice(np.asarray(history, dtype=float), size=shape)
    # Each draw comes from history with probability history_weight, else from the default.
    use_history = rng.random(shape) < history_weight(len(history))
    return np.where(use_history, history_weeks, default_weeks)


def simulate_future_hours(history, days_left, simulations, rng):
    """One number per simulation: total hours in the rest of the month."""
    full_weeks, extra_days = divmod(days_left, DAYS_PER_WEEK)
    # Column i = week i. The last column is the partial week.
    draws = sample_weeks(history, (simulations, full_weeks + 1), rng)
    week_fractions = np.ones(full_weeks + 1)
    week_fractions[-1] = extra_days / DAYS_PER_WEEK   # e.g. 3 days = 3/7 of a week
    return draws @ week_fractions                     # sum of (week hours x fraction)


def summarize(final_hours, target):
    p10, p50, p90 = np.percentile(final_hours, [10, 50, 90])
    return {
        "probability": round(float(np.mean(final_hours >= target)), 3),
        "percentiles": {"p10": round(float(p10), 1), "p50": round(float(p50), 1), "p90": round(float(p90), 1)},
    }


def forecast(logged_hours_this_month, past_weekly_totals, days_left, target=80,
             what_if_extra_hours=0, simulations=SIMULATIONS, seed=None):
    """Estimate the chance of reaching `target` hours by the end of the month.

    days_left: days still ahead in the month that could have hours (count today
               if the person may still log hours today).
    seed:      makes results repeatable (used by tests).
    """
    if logged_hours_this_month < 0 or what_if_extra_hours < 0:
        raise ValueError("hours can't be negative")
    if days_left < 0:
        raise ValueError("days_left can't be negative")
    if target <= 0:
        raise ValueError("target must be positive")
    if any(week < 0 for week in past_weekly_totals):
        raise ValueError("weekly totals can't be negative")

    rng = np.random.default_rng(seed)
    future = simulate_future_hours(past_weekly_totals, days_left, simulations, rng)
    final = logged_hours_this_month + future

    result = {
        **summarize(final, target),
        "target": target,
        "hours_needed": round(max(target - logged_hours_this_month, 0), 2),
        "simulations": simulations,
        "weeks_of_history": len(past_weekly_totals),
        "history_weight": round(history_weight(len(past_weekly_totals)), 3),
        "what_if": None,
    }

    if what_if_extra_hours > 0:
        # Same 10,000 futures, just with the extra hours added: so any change in
        # the answer comes from the extra hours, not from new random numbers.
        result["what_if"] = {
            "extra_hours": what_if_extra_hours,
            **summarize(final + what_if_extra_hours, target),
        }
    return result
