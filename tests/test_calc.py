from walks.calc import (
    get_tier_for_time, calculate_leg_times, find_solar_events,
    format_time, format_time_of_day, format_diff,
)


# --- get_tier_for_time ---

def test_get_tier_first_tier() -> None:
    tiers = [
        {'up_to_minutes': 120, 'flat_pace_min_per_km': 5.0, 'ascent_pace_min_per_125m': 5.0, 'descent_pace_min_per_375m': 5.0},
        {'up_to_minutes': None, 'flat_pace_min_per_km': 7.0, 'ascent_pace_min_per_125m': 7.0, 'descent_pace_min_per_375m': 7.0},
    ]
    idx, tier = get_tier_for_time(tiers, 60)
    assert idx == 0
    assert tier['flat_pace_min_per_km'] == 5.0


def test_get_tier_second_tier() -> None:
    tiers = [
        {'up_to_minutes': 120, 'flat_pace_min_per_km': 5.0, 'ascent_pace_min_per_125m': 5.0, 'descent_pace_min_per_375m': 5.0},
        {'up_to_minutes': None, 'flat_pace_min_per_km': 7.0, 'ascent_pace_min_per_125m': 7.0, 'descent_pace_min_per_375m': 7.0},
    ]
    idx, tier = get_tier_for_time(tiers, 150)
    assert idx == 1
    assert tier['flat_pace_min_per_km'] == 7.0


def test_get_tier_empty() -> None:
    idx, tier = get_tier_for_time([], 0)
    assert idx == 0
    assert tier is None


def test_get_tier_boundary() -> None:
    tiers = [
        {'up_to_minutes': 120, 'flat_pace_min_per_km': 5.0, 'ascent_pace_min_per_125m': 5.0, 'descent_pace_min_per_375m': 5.0},
        {'up_to_minutes': None, 'flat_pace_min_per_km': 7.0, 'ascent_pace_min_per_125m': 7.0, 'descent_pace_min_per_375m': 7.0},
    ]
    # Exactly at boundary should move to next tier
    idx, tier = get_tier_for_time(tiers, 120)
    assert idx == 1


# --- calculate_leg_times ---

def test_calculate_leg_times_basic() -> None:
    legs = [
        {'id': 1, 'leg_num': 1, 'location': 'Start', 'distance_km': 0, 'ascent_m': 0, 'descent_m': 0, 'notes': ''},
        {'id': 2, 'leg_num': 2, 'location': 'CP1', 'distance_km': 10.0, 'ascent_m': 0, 'descent_m': 0, 'notes': ''},
    ]
    tiers = [
        {'up_to_minutes': None, 'flat_pace_min_per_km': 6.0, 'ascent_pace_min_per_125m': 0, 'descent_pace_min_per_375m': 0},
    ]
    result = calculate_leg_times(legs, tiers)
    assert result[0]['time'] == 0.0
    assert result[1]['time'] == 60.0
    assert result[1]['cumulative_time'] == 60.0
    assert result[1]['cumulative_distance'] == 10.0


def test_calculate_leg_times_with_ascent() -> None:
    legs = [
        {'id': 1, 'leg_num': 1, 'location': 'Start', 'distance_km': 0, 'ascent_m': 0, 'descent_m': 0},
        {'id': 2, 'leg_num': 2, 'location': 'Summit', 'distance_km': 5.0, 'ascent_m': 500, 'descent_m': 0},
    ]
    tiers = [
        {'up_to_minutes': None, 'flat_pace_min_per_km': 6.0, 'ascent_pace_min_per_125m': 5.0, 'descent_pace_min_per_375m': 0},
    ]
    result = calculate_leg_times(legs, tiers)
    # 5km * 6min + 500m / 125m * 5min = 30 + 20 = 50
    assert result[1]['time'] == 50.0


def test_calculate_leg_times_with_override() -> None:
    legs = [
        {'id': 1, 'leg_num': 1, 'location': 'Start', 'distance_km': 0, 'ascent_m': 0, 'descent_m': 0},
        {'id': 2, 'leg_num': 2, 'location': 'CP1', 'distance_km': 10.0, 'ascent_m': 0, 'descent_m': 0},
    ]
    tiers = [
        {'up_to_minutes': None, 'flat_pace_min_per_km': 6.0, 'ascent_pace_min_per_125m': 0, 'descent_pace_min_per_375m': 0},
    ]
    result = calculate_leg_times(legs, tiers, overrides={2: 45.0})
    assert result[1]['calc_time'] == 60.0
    assert result[1]['override'] == 45.0
    assert result[1]['time'] == 45.0


def test_calculate_leg_times_with_start_time() -> None:
    legs = [
        {'id': 1, 'leg_num': 1, 'location': 'Start', 'distance_km': 0, 'ascent_m': 0, 'descent_m': 0},
        {'id': 2, 'leg_num': 2, 'location': 'CP1', 'distance_km': 10.0, 'ascent_m': 0, 'descent_m': 0},
    ]
    tiers = [
        {'up_to_minutes': None, 'flat_pace_min_per_km': 6.0, 'ascent_pace_min_per_125m': 0, 'descent_pace_min_per_375m': 0},
    ]
    result = calculate_leg_times(legs, tiers, start_time_minutes=360)  # 06:00
    assert result[0]['time_of_day'] == 360.0  # arrives at start at 06:00
    assert result[1]['time_of_day'] == 420.0  # arrives at CP1 at 07:00


def test_calculate_no_tiers() -> None:
    legs = [
        {'id': 1, 'leg_num': 1, 'location': 'Start', 'distance_km': 5.0, 'ascent_m': 100, 'descent_m': 0},
    ]
    result = calculate_leg_times(legs, [])
    assert result[0]['time'] == 0.0


# --- find_solar_events ---

def test_find_solar_events() -> None:
    legs = [
        {'leg_num': 1, 'time': 0},
        {'leg_num': 2, 'time': 120},  # 2 hours
        {'leg_num': 3, 'time': 180},  # 3 hours
    ]
    solar = {
        'sunrise': 5.0, 'sunset': 21.0,
        'solar_noon': 13.0, 'daylight_hours': 16.0,
        'sunrise_str': '05:00', 'sunset_str': '21:00',
        'solar_noon_str': '13:00', 'daylight_str': '16:00',
        'timezone': 'BST',
    }
    # Start at 04:00 (240 min). Sunrise at 05:00 (300 min).
    # Leg 1 ends at 04:00, leg 2 ends at 06:00 — sunrise falls in leg 2.
    result = find_solar_events(legs, 240, solar)
    assert result['sunrise_leg'] == 2


def test_find_solar_events_no_solar() -> None:
    result = find_solar_events([], 360, {})
    assert result['sunrise_leg'] is None
    assert result['sunset_leg'] is None


# --- format_time ---

def test_format_time_hours() -> None:
    assert format_time(90) == '1:30:00'


def test_format_time_minutes() -> None:
    assert format_time(25.5) == '25:30'


def test_format_time_none() -> None:
    assert format_time(None) == ''


def test_format_time_zero() -> None:
    assert format_time(0) == '0:00'


# --- format_time_of_day ---

def test_format_time_of_day() -> None:
    assert format_time_of_day(390) == '06:30'


def test_format_time_of_day_none() -> None:
    assert format_time_of_day(None) == ''


def test_format_time_of_day_wraps() -> None:
    # 25 hours = 01:00 next day
    assert format_time_of_day(1500) == '01:00'


# --- format_diff ---

def test_format_diff_positive() -> None:
    assert format_diff(10) == '+10:00'


def test_format_diff_negative() -> None:
    assert format_diff(-5.5) == '-5:30'


def test_format_diff_none() -> None:
    assert format_diff(None) == ''
