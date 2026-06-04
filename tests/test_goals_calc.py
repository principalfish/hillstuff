import datetime

from goals import calc

# The source spreadsheet's reference date.
REF = datetime.date(2026, 6, 4)


class TestDates:
    def test_days_in_year(self) -> None:
        assert calc.days_in_year(2026) == 365
        assert calc.days_in_year(2024) == 366  # leap

    def test_days_elapsed_matches_spreadsheet(self) -> None:
        assert calc.days_elapsed(2026, REF) == 155

    def test_days_elapsed_before_year(self) -> None:
        assert calc.days_elapsed(2026, datetime.date(2025, 12, 31)) == 0

    def test_days_elapsed_after_year(self) -> None:
        assert calc.days_elapsed(2026, datetime.date(2027, 1, 1)) == 365

    def test_year_progress(self) -> None:
        yp = calc.year_progress(2026, REF)
        assert yp.days_elapsed == 155
        assert yp.days_remaining == 210
        assert round(yp.weeks_remaining, 2) == 30.0


class TestGoalStatus:
    def test_distance_rates(self) -> None:
        yp = calc.year_progress(2026, REF)
        st = calc.goal_status(3220, 1325.5, yp)
        assert round(st.per_week_start, 1) == 61.8
        # (3220-1325.5)/30 = 63.15 exactly (spreadsheet shows 63.2, rounded up).
        assert round(st.per_week_now, 2) == 63.15
        # Expected to date 3220*155/365 = 1367.4 > 1325.5 -> behind.
        assert st.on_track is False
        assert round(st.projected_year_end, 0) == 3121

    def test_elevation_rates(self) -> None:
        yp = calc.year_progress(2026, REF)
        st = calc.goal_status(200000, 87083, yp)
        assert round(st.per_week_start, 1) == 3835.6
        assert round(st.per_week_now, 1) == 3763.9

    def test_time_rates(self) -> None:
        yp = calc.year_progress(2026, REF)
        st = calc.goal_status(365, 165, yp)
        assert round(st.per_week_start, 2) == 7.00
        assert round(st.per_week_now, 2) == 6.67

    def test_on_track_when_ahead(self) -> None:
        yp = calc.year_progress(2026, REF)
        st = calc.goal_status(100, 90, yp)  # expected 42.5, 90 >= 42.5
        assert st.on_track is True

    def test_pct(self) -> None:
        yp = calc.year_progress(2026, REF)
        st = calc.goal_status(200, 50, yp)
        assert st.pct == 25.0

    def test_zero_days_elapsed_guards(self) -> None:
        yp = calc.year_progress(2026, datetime.date(2025, 1, 1))  # elapsed 0
        st = calc.goal_status(100, 0, yp)
        assert st.projected_year_end is None

    def test_no_weeks_remaining_guards(self) -> None:
        yp = calc.year_progress(2026, datetime.date(2027, 1, 1))  # year over
        st = calc.goal_status(100, 50, yp)
        assert st.per_week_now is None


class TestExtrapolate:
    def test_run_distance(self) -> None:
        yp = calc.year_progress(2026, REF)
        per_day, per_week, per_year = calc.extrapolate(1325.5, yp)
        assert round(per_day, 1) == 8.6
        assert round(per_year, 0) == 3121

    def test_zero_elapsed_returns_none(self) -> None:
        yp = calc.year_progress(2026, datetime.date(2025, 6, 1))
        assert calc.extrapolate(100, yp) == (None, None, None)


class TestGoalProgress:
    GRID = {
        'run': {'distance': 100.0, 'elevation': 500.0, 'time': 10.0},
        'walk': {'distance': 40.0, 'elevation': 800.0, 'time': 20.0},
        'cycle': {'distance': 200.0, 'elevation': 100.0, 'time': 5.0},
    }

    def test_single_activity(self) -> None:
        assert calc.goal_progress('distance', ['run'], self.GRID) == 100.0

    def test_combined_activities(self) -> None:
        assert calc.goal_progress('elevation', ['run', 'walk'], self.GRID) == 1300.0

    def test_all_activities(self) -> None:
        assert calc.goal_progress('time', ['run', 'walk', 'cycle'], self.GRID) == 35.0

    def test_unknown_activity_is_zero(self) -> None:
        assert calc.goal_progress('distance', ['ski'], self.GRID) == 0.0
