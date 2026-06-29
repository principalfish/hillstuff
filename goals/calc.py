"""Pure, typed helpers for the yearly-goals dashboard.

All numbers reconcile with the source spreadsheet for 2026-06-04:
days_elapsed=155, days_remaining=210; distance/week start 3220*7/365=61.8,
distance/week now (3220-1325.5)/30=63.2; time/week now (365-165)/30=6.67.
"""
import calendar
import datetime
from dataclasses import dataclass
from typing import Iterable

GOAL_TYPES = ('distance', 'elevation', 'time')

GOAL_TYPE_LABELS: dict[str, str] = {
    'distance': 'Distance',
    'elevation': 'Elevation',
    'time': 'Time',
}
GOAL_TYPE_UNITS: dict[str, str] = {
    'distance': 'km',
    'elevation': 'm',
    'time': 'h',
}


def days_in_year(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


def days_elapsed(year: int, ref: datetime.date) -> int:
    """Whole days of `year` completed as of `ref`, clamped to [0, days_in_year]."""
    if ref.year < year:
        return 0
    if ref.year > year:
        return days_in_year(year)
    return ref.timetuple().tm_yday


@dataclass
class YearProgress:
    year: int
    as_of: datetime.date
    days_in_year: int
    days_elapsed: int
    days_remaining: int
    weeks_elapsed: float
    weeks_remaining: float


def year_progress(year: int, ref: datetime.date) -> YearProgress:
    total = days_in_year(year)
    elapsed = days_elapsed(year, ref)
    remaining = total - elapsed
    return YearProgress(
        year=year,
        as_of=ref,
        days_in_year=total,
        days_elapsed=elapsed,
        days_remaining=remaining,
        weeks_elapsed=elapsed / 7,
        weeks_remaining=remaining / 7,
    )


@dataclass
class GoalStatus:
    progress: float
    target: float
    pct: float | None
    expected_to_date: float | None
    on_track: bool
    per_week_start: float | None
    per_week_now: float | None
    projected_year_end: float | None


def active_day_counts(year: int, periods: Iterable[tuple[str, str]],
                      ref: datetime.date) -> tuple[int, int]:
    """Count active days across `periods`, clamped to `year` and de-duplicated.

    `periods` is an iterable of (start_iso, end_iso) inclusive ranges. Returns
    (total_active_days, elapsed_active_days) where elapsed counts active days on
    or before `ref`. Invalid or reversed ranges are skipped.
    """
    year_start = datetime.date(year, 1, 1)
    year_end = datetime.date(year, 12, 31)
    days: set[int] = set()
    for start_iso, end_iso in periods:
        try:
            start = datetime.date.fromisoformat(start_iso)
            end = datetime.date.fromisoformat(end_iso)
        except (ValueError, TypeError):
            continue
        if end < start:
            continue
        start = max(start, year_start)
        end = min(end, year_end)
        days.update(range(start.toordinal(), end.toordinal() + 1))
    ref_ord = ref.toordinal()
    elapsed = sum(1 for o in days if o <= ref_ord)
    return len(days), elapsed


def goal_status(target: float, progress: float, yp: YearProgress,
                window_total: int | None = None,
                window_elapsed: int | None = None) -> GoalStatus:
    # Default window is the whole year. A goal with active periods passes its
    # active-day total/elapsed so pacing ignores days outside those periods.
    total = window_total if window_total is not None else yp.days_in_year
    elapsed = window_elapsed if window_elapsed is not None else yp.days_elapsed
    remaining = max(total - elapsed, 0)
    weeks_remaining = remaining / 7
    pct = (progress / target * 100) if target else None
    expected = (target * elapsed / total) if total else None
    on_track = progress >= expected if expected is not None else True
    per_week_start = (target * 7 / total) if total else None
    per_week_now = (max(target - progress, 0.0) / weeks_remaining
                    if weeks_remaining > 0 else None)
    projected = (progress / elapsed * total) if elapsed > 0 else None
    return GoalStatus(
        progress=progress,
        target=target,
        pct=pct,
        expected_to_date=expected,
        on_track=on_track,
        per_week_start=per_week_start,
        per_week_now=per_week_now,
        projected_year_end=projected,
    )


def extrapolate(value: float, yp: YearProgress) -> tuple[float | None, float | None, float | None]:
    """Return (per_day, per_week, projected_year_end) for a current-state value."""
    if yp.days_elapsed <= 0:
        return (None, None, None)
    per_day = value / yp.days_elapsed
    return (per_day, per_day * 7, per_day * yp.days_in_year)


def goal_progress(goal_type: str, activity_types: Iterable[str],
                  grid: dict[str, dict[str, float]]) -> float:
    """Sum a goal's metric across its activity types.

    `grid` maps activity_type -> {goal_type -> value}, letting a goal combine
    e.g. 'run' + 'walk' elevation.
    """
    return sum(grid.get(at, {}).get(goal_type, 0.0) for at in activity_types)
