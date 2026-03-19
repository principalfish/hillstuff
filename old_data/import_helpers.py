"""Shared helpers for importing big run routes from CSVs."""
import csv
import os
import sys

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from walks.db import db
from walks.models import Route, Leg, PaceTier, Attempt, AttemptLeg


def get_app_context():  # type: ignore[no-untyped-def]
    """Create app and return context manager."""
    return create_app().app_context()


def delete_route(name: str) -> None:
    """Delete an existing route by name."""
    existing = Route.query.filter_by(name=name).first()
    if existing:
        db.session.delete(existing)
        db.session.flush()


def create_route(
    name: str,
    latitude: float,
    longitude: float,
    start_time: str,
    start_date: str,
) -> Route:
    """Create a new route and return it."""
    route = Route(
        name=name,
        latitude=latitude,
        longitude=longitude,
        start_time=start_time,
        start_date=start_date,
    )
    db.session.add(route)
    db.session.flush()
    return route


def add_pace_tiers(
    route_id: int,
    tiers: list[tuple[float | None, float, float, float]],
) -> None:
    """Add pace tiers. Each tuple: (up_to_minutes, flat, ascent, descent)."""
    for up_to, flat, asc, desc in tiers:
        db.session.add(PaceTier(
            route_id=route_id,
            up_to_minutes=up_to,
            flat_pace_min_per_km=flat,
            ascent_pace_min_per_125m=asc,
            descent_pace_min_per_375m=desc,
        ))


def add_leg(
    route_id: int,
    leg_num: int,
    location: str,
    distance_km: float,
    ascent_m: float,
    descent_m: float,
    notes: str = '',
) -> Leg:
    """Add a leg and return it."""
    leg = Leg(
        route_id=route_id,
        leg_num=leg_num,
        location=location,
        distance_km=distance_km,
        ascent_m=ascent_m,
        descent_m=descent_m,
        notes=notes,
    )
    db.session.add(leg)
    db.session.flush()
    return leg


def add_attempt(
    route_id: int,
    name: str,
    date: str | None,
    legs: list[Leg],
    leg_minutes: list[float | None],
) -> None:
    """Add an attempt with per-leg times."""
    attempt = Attempt(
        route_id=route_id,
        name=name,
        date=date,
        notes='',
    )
    db.session.add(attempt)
    db.session.flush()

    for leg, mins in zip(legs, leg_minutes):
        db.session.add(AttemptLeg(
            attempt_id=attempt.id,
            leg_id=leg.id,
            actual_time_minutes=mins,
        ))


def safe_float(val: str) -> float:
    """Parse a float, returning 0 for empty/error values."""
    val = val.strip()
    if not val or val.startswith('Err') or val == '-':
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def parse_minutes(val: str) -> float | None:
    """Parse a minutes value. Returns None for empty/zero/error."""
    val = val.strip()
    if not val or val == '0' or val.startswith('Err'):
        return None
    try:
        v = float(val)
        return v if v > 0 else None
    except ValueError:
        return None


def read_csv(filename: str) -> list[list[str]]:
    """Read a CSV from old_data/ directory."""
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, newline='') as f:
        return list(csv.reader(f))
