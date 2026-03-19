from datetime import datetime
from walks.solar import solar_times, _is_bst, _hours_to_hhmm


# --- solar_times ---

def test_solar_times_summer() -> None:
    result = solar_times(56.8, -5.1, '2026-06-21')
    assert result is not None
    assert result['timezone'] == 'BST'
    assert 3.0 < result['sunrise'] < 6.0
    assert 20.0 < result['sunset'] < 23.0
    assert result['daylight_hours'] > 16


def test_solar_times_winter() -> None:
    result = solar_times(56.8, -5.1, '2026-12-21')
    assert result is not None
    assert result['timezone'] == 'GMT'
    assert result['daylight_hours'] < 8


def test_solar_times_returns_strings() -> None:
    result = solar_times(56.8, -5.1, '2026-06-01')
    assert result is not None
    assert ':' in result['sunrise_str']
    assert ':' in result['sunset_str']


def test_solar_times_equator() -> None:
    result = solar_times(0, 0, '2026-03-21')
    assert result is not None
    assert 11.5 < result['daylight_hours'] < 12.5


# --- _is_bst ---

def test_is_bst_summer() -> None:
    assert _is_bst(datetime(2026, 7, 1)) is True


def test_is_bst_winter() -> None:
    assert _is_bst(datetime(2026, 1, 15)) is False


def test_is_bst_march_before() -> None:
    # 2026: last Sunday of March is March 29
    assert _is_bst(datetime(2026, 3, 28)) is False


def test_is_bst_march_after() -> None:
    assert _is_bst(datetime(2026, 3, 30)) is True


def test_is_bst_october_before() -> None:
    # 2026: last Sunday of October is October 25
    assert _is_bst(datetime(2026, 10, 24)) is True


# --- _hours_to_hhmm ---

def test_hours_to_hhmm() -> None:
    assert _hours_to_hhmm(6.5) == '06:30'


def test_hours_to_hhmm_midnight() -> None:
    assert _hours_to_hhmm(0.0) == '00:00'


def test_hours_to_hhmm_rounding() -> None:
    # 59.5 seconds should round to 1 minute
    assert _hours_to_hhmm(12.9917) == '13:00'
