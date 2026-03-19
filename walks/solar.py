"""Simple solar position calculator for sunrise/sunset times."""
import math
from datetime import datetime, timedelta
from typing import TypedDict


class SolarResult(TypedDict):
    sunrise: float
    sunset: float
    solar_noon: float
    daylight_hours: float
    sunrise_str: str
    sunset_str: str
    solar_noon_str: str
    daylight_str: str
    timezone: str


def solar_times(lat: float, lon: float, date_str: str) -> SolarResult | None:
    """Calculate sunrise, sunset, solar noon for a given location and date.

    Returns dict with times as fractional hours (UTC), or None for polar extremes.
    Automatically adjusts for BST (last Sunday March to last Sunday October).
    """
    date = datetime.strptime(date_str, '%Y-%m-%d')
    day_of_year = date.timetuple().tm_yday

    # Solar declination
    declination = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))

    lat_rad = math.radians(lat)
    dec_rad = math.radians(declination)

    # Hour angle for sunrise/sunset (accounting for atmospheric refraction)
    cos_ha = (
        -math.sin(math.radians(-0.833)) - math.sin(lat_rad) * math.sin(dec_rad)
    ) / (math.cos(lat_rad) * math.cos(dec_rad))

    if cos_ha > 1:
        return None  # Polar night
    if cos_ha < -1:
        return None  # Midnight sun

    hour_angle = math.degrees(math.acos(cos_ha))

    # Equation of time correction
    b = math.radians(360 / 365 * (day_of_year - 81))
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

    # Solar noon in UTC hours (lon in degrees, 4 min per degree)
    solar_noon = 12 - (eot + 4 * lon) / 60

    sunrise_utc = solar_noon - hour_angle / 15
    sunset_utc = solar_noon + hour_angle / 15
    daylight = 2 * hour_angle / 15

    # BST offset
    offset = 1 if _is_bst(date) else 0

    sunrise = sunrise_utc + offset
    sunset = sunset_utc + offset
    noon = solar_noon + offset

    return {
        'sunrise': sunrise,
        'sunset': sunset,
        'solar_noon': noon,
        'daylight_hours': daylight,
        'sunrise_str': _hours_to_hhmm(sunrise),
        'sunset_str': _hours_to_hhmm(sunset),
        'solar_noon_str': _hours_to_hhmm(noon),
        'daylight_str': _hours_to_hhmm(daylight),
        'timezone': 'BST' if offset else 'GMT',
    }


def _is_bst(date: datetime) -> bool:
    """Check if a date falls within British Summer Time."""
    year = date.year
    # Last Sunday of March
    march_last = datetime(year, 3, 31)
    bst_start = march_last - timedelta(days=march_last.weekday() + 1 % 7)
    if march_last.weekday() == 6:
        bst_start = march_last
    else:
        bst_start = march_last - timedelta(days=(march_last.weekday() + 1) % 7)

    # Last Sunday of October
    oct_last = datetime(year, 10, 31)
    if oct_last.weekday() == 6:
        bst_end = oct_last
    else:
        bst_end = oct_last - timedelta(days=(oct_last.weekday() + 1) % 7)

    return bst_start <= date < bst_end


def _hours_to_hhmm(hours: float) -> str:
    """Convert fractional hours to HH:MM string."""
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f'{h:02d}:{m:02d}'
