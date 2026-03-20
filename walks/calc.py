from typing import Any

from walks.solar import SolarResult

LegDict = dict[str, Any]
TierDict = dict[str, Any]
SolarEventsDict = dict[str, int | float | None]


def get_tier_for_time(
    pace_tiers: list[TierDict], cumulative_minutes: float
) -> tuple[int, TierDict | None]:
    """Return the pace tier active at a given cumulative time.

    pace_tiers should be sorted by up_to_minutes ascending, with the
    unbounded tier (up_to_minutes=None) last.
    """
    for i, tier in enumerate(pace_tiers):
        if tier['up_to_minutes'] is None or cumulative_minutes < tier['up_to_minutes']:
            return i, tier
    return (len(pace_tiers) - 1, pace_tiers[-1]) if pace_tiers else (0, None)


def calculate_leg_times(
    legs: list[LegDict],
    pace_tiers: list[TierDict],
    overrides: dict[int, float] | None = None,
    start_time_minutes: float | None = None,
) -> list[LegDict]:
    """Calculate time and cumulatives for each leg.

    Args:
        legs: list of dicts with distance_km, ascent_m, descent_m, id
        pace_tiers: list of dicts sorted by up_to_minutes (None last)
        overrides: dict of {leg_id: override_minutes}
        start_time_minutes: start time as minutes from midnight (e.g. 480 = 08:00)

    Returns:
        list of dicts with all leg info plus calc_time, time, cumulative_*, time_of_day
    """
    if overrides is None:
        overrides = {}

    cumulative_time: float = 0.0
    cumulative_dist: float = 0.0
    cumulative_ascent: float = 0.0
    cumulative_descent: float = 0.0
    results: list[LegDict] = []

    for leg in legs:
        tier_index, tier = get_tier_for_time(pace_tiers, cumulative_time)

        if tier:
            calc_time = (
                leg['distance_km'] * tier['flat_pace_min_per_km']
                + leg['ascent_m'] / 125.0 * tier['ascent_pace']
                + leg['descent_m'] / 500.0 * tier['descent_pace']
            )
        else:
            calc_time = 0.0

        override = overrides.get(leg['id'])
        time = override if override is not None else calc_time

        cumulative_time += time

        # Time of day at arrival at this location
        time_of_day: float | None = None
        if start_time_minutes is not None:
            time_of_day = start_time_minutes + cumulative_time
        cumulative_dist += leg['distance_km']
        cumulative_ascent += leg['ascent_m']
        cumulative_descent += leg['descent_m']

        results.append({
            'id': leg['id'],
            'leg_num': leg['leg_num'],
            'location': leg['location'],
            'distance_km': leg['distance_km'],
            'ascent_m': leg['ascent_m'],
            'descent_m': leg['descent_m'],
            'notes': leg.get('notes', ''),
            'calc_time': calc_time,
            'override': override,
            'time': time,
            'cumulative_distance': cumulative_dist,
            'cumulative_ascent': cumulative_ascent,
            'cumulative_descent': cumulative_descent,
            'cumulative_time': cumulative_time,
            'time_of_day': time_of_day,
            'tier_index': tier_index,
        })

    return results


def find_solar_events(
    legs: list[LegDict],
    start_time_minutes: float,
    solar: SolarResult,
) -> SolarEventsDict:
    """Find which legs sunrise/sunset fall within.

    Returns dict with 'sunrise_leg' and 'sunset_leg' (leg_num or None).
    """
    if not solar or start_time_minutes is None:
        return {'sunrise_leg': None, 'sunset_leg': None,
                'sunrise_cum_time': None, 'sunset_cum_time': None}

    sunrise_min: float = solar['sunrise'] * 60
    sunset_min: float = solar['sunset'] * 60

    result: SolarEventsDict = {
        'sunrise_leg': None, 'sunset_leg': None,
        'sunrise_cum_time': None, 'sunset_cum_time': None,
    }

    cum_time: float = 0.0
    for leg in legs:
        leg_start_tod = start_time_minutes + cum_time
        cum_time += leg['time']
        leg_end_tod = start_time_minutes + cum_time

        if result['sunrise_leg'] is None and leg_start_tod <= sunrise_min <= leg_end_tod:
            result['sunrise_leg'] = leg['leg_num']
            result['sunrise_cum_time'] = sunrise_min - start_time_minutes

        if result['sunset_leg'] is None and leg_start_tod <= sunset_min <= leg_end_tod:
            result['sunset_leg'] = leg['leg_num']
            result['sunset_cum_time'] = sunset_min - start_time_minutes

    return result


def format_time(minutes: float | None) -> str:
    """Format minutes as H:MM:SS or M:SS."""
    if minutes is None:
        return ''
    total_seconds = int(round(minutes * 60))
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f'{hours}:{mins:02d}:{secs:02d}'
    return f'{mins}:{secs:02d}'


def format_time_of_day(minutes: float | None) -> str:
    """Format minutes-from-midnight as HH:MM."""
    if minutes is None:
        return ''
    total_min = int(round(minutes))
    h = (total_min // 60) % 24
    m = total_min % 60
    return f'{h:02d}:{m:02d}'


def format_diff(minutes: float | None) -> str:
    """Format a time difference with +/- prefix."""
    if minutes is None:
        return ''
    sign = '+' if minutes >= 0 else '-'
    return sign + format_time(abs(minutes))
