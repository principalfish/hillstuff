"""Create walks_template.db: hill lists (no ascents) + big runs (FW only, more pace tiers).

Run from project root:
    python create_template_db.py
"""
import csv
import os
import sys

PROJECT_ROOT = os.path.dirname(__file__)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'old_data'))

from flask import Flask
import walks.models  # noqa: F401 — registers models with SQLAlchemy
import hills.models  # noqa: F401 — registers hills models with SQLAlchemy
from walks.db import db
from hills.models import Hill
from walks.models import Route, Leg, PaceTier, Attempt, AttemptLeg

TEMPLATE_DB = os.path.join(PROJECT_ROOT, 'walks_template.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{TEMPLATE_DB}'
app.secret_key = 'dev'
db.init_app(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_float(val: str) -> float:
    val = val.strip()
    if not val or val.startswith('Err') or val == '-':
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def parse_minutes(val: str) -> float | None:
    val = val.strip()
    if not val or val == '0' or val.startswith('Err'):
        return None
    try:
        v = float(val)
        return v if v > 0 else None
    except ValueError:
        return None


def read_csv(filename: str) -> list[list[str]]:
    path = os.path.join(PROJECT_ROOT, 'old_data', filename)
    with open(path, newline='') as f:
        return list(csv.reader(f))


def add_pace_tiers(route_id: int, tiers: list[tuple[float | None, float, float, float]]) -> None:
    for up_to, flat, asc, desc in tiers:
        db.session.add(PaceTier(
            route_id=route_id,
            up_to_minutes=up_to,
            flat_pace_min_per_km=flat,
            ascent_pace_min_per_125m=asc,
            descent_pace_min_per_375m=desc,
        ))


def add_leg(route_id: int, leg_num: int, location: str,
            distance_km: float, ascent_m: float, descent_m: float,
            notes: str = '') -> Leg:
    leg = Leg(route_id=route_id, leg_num=leg_num, location=location,
              distance_km=distance_km, ascent_m=ascent_m, descent_m=descent_m, notes=notes)
    db.session.add(leg)
    db.session.flush()
    return leg


def add_attempt(route_id: int, name: str, date: str | None,
                legs: list[Leg], leg_minutes: list[float | None]) -> None:
    attempt = Attempt(route_id=route_id, name=name, date=date, notes='')
    db.session.add(attempt)
    db.session.flush()
    for leg, mins in zip(legs, leg_minutes):
        db.session.add(AttemptLeg(
            attempt_id=attempt.id,
            leg_id=leg.id,
            actual_time_minutes=mins,
        ))


def round_min(val: float | None) -> float | None:
    return round(val) if val is not None else None


# ---------------------------------------------------------------------------
# Hills (no ascents)
# ---------------------------------------------------------------------------

def import_munros() -> None:
    with open(os.path.join(PROJECT_ROOT, 'old_data', 'munro.csv'), newline='') as f:
        reader = csv.reader(f)
        next(reader)
        count = 0
        for row in reader:
            name = row[6].strip()
            if not name:
                continue
            db.session.add(Hill(
                name=name,
                height_m=int(row[7]),
                rank=int(row[9]),
                region=row[11].strip(),
                hill_type='munro',
            ))
            count += 1
    db.session.flush()
    print(f'Munros: {count}')


def import_corbetts() -> None:
    with open(os.path.join(PROJECT_ROOT, 'old_data', 'corbetts.csv'), newline='') as f:
        reader = csv.reader(f)
        next(reader)
        count = 0
        for row in reader:
            name = row[6].strip()
            if not name:
                continue
            db.session.add(Hill(
                name=name,
                height_m=int(round(float(row[7]))),
                rank=int(row[9]),
                region=row[10].strip(),
                hill_type='corbett',
            ))
            count += 1
    db.session.flush()
    print(f'Corbetts: {count}')


BOOK_REGIONS: dict[str, str] = {
    'E': 'Eastern Fells', 'FE': 'Far Eastern Fells', 'C': 'Central Fells',
    'S': 'Southern Fells', 'N': 'Northern Fells', 'NW': 'North Western Fells',
    'W': 'Western Fells',
}


def import_wainwrights() -> None:
    with open(os.path.join(PROJECT_ROOT, 'old_data', 'wainwrights.csv'), newline='') as f:
        reader = csv.reader(f)
        next(reader)
        count = 0
        for row in reader:
            name = row[1].strip()
            if not name:
                continue
            rank_str = row[0].strip()
            if not rank_str.isdigit():
                continue
            height_m = round(int(row[2]) * 0.3048)
            db.session.add(Hill(
                name=name,
                height_m=height_m,
                rank=int(rank_str),
                region=BOOK_REGIONS.get(row[5].strip(), row[5].strip()),
                hill_type='wainwright',
            ))
            count += 1
    db.session.flush()
    print(f'Wainwrights: {count}')


# ---------------------------------------------------------------------------
# Big runs
# ---------------------------------------------------------------------------

def import_ramsay() -> None:
    rows = read_csv('ramsay.csv')
    route = Route(name="Ramsay's Round", latitude=56.83, longitude=-5.10,
                  start_time='00:00', start_date='2026-07-11')
    db.session.add(route)
    db.session.flush()

    add_pace_tiers(route.id, [
        (60,   6.0, 6.0, 6.0),
        (180,  6.5, 6.5, 6.5),
        (240,  7.0, 7.0, 7.0),
        (300,  7.5, 7.5, 7.5),
        (540,  8.0, 8.0, 8.0),
        (None, 8.5, 8.5, 8.5),
    ])

    legs: list[Leg] = []
    for i in range(14, 44):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(route.id, len(legs) + 1, loc,
                      distance_km=safe_float(row[4]),
                      ascent_m=safe_float(row[5]),
                      descent_m=safe_float(row[6]),
                      notes=row[11].strip() if len(row) > 11 else '')
        legs.append(leg)
        if loc == 'Youth Hostel' and len(legs) > 1:
            break

    fw_mins = [round_min(parse_minutes(rows[14 + j][42])) if len(rows[14 + j]) > 42 else None
               for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, fw_mins)
    print(f"Ramsay's Round: {len(legs)} legs, 1 attempt")


def import_tranters() -> None:
    rows = read_csv('tranters.csv')
    route = Route(name="Tranter's Round", latitude=56.83, longitude=-5.10,
                  start_time='02:00', start_date='2026-06-01')
    db.session.add(route)
    db.session.flush()

    add_pace_tiers(route.id, [
        (60,   6.0, 6.0, 6.0),
        (180,  6.5, 6.5, 6.5),
        (300,  7.0, 7.0, 7.0),
        (420,  7.5, 7.5, 7.5),
        (540,  8.0, 8.0, 8.0),
        (None, 8.5, 8.5, 8.5),
    ])

    legs: list[Leg] = []
    for i in range(14, 35):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(route.id, len(legs) + 1, loc,
                      distance_km=safe_float(row[1]),
                      ascent_m=safe_float(row[2]),
                      descent_m=safe_float(row[3]),
                      notes=row[8].strip() if len(row) > 8 else '')
        legs.append(leg)
        if loc == 'Youth Hostel' and len(legs) > 1:
            break

    fw_mins = [round_min(parse_minutes(rows[14 + j][29])) if len(rows[14 + j]) > 29 else None
               for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, fw_mins)
    print(f"Tranter's Round: {len(legs)} legs, 1 attempt")


def import_lochaber() -> None:
    rows = read_csv('lochaber_traverse.csv')
    route = Route(name='Lochaber Traverse', latitude=56.83, longitude=-5.10,
                  start_time='05:00', start_date='2026-09-02')
    db.session.add(route)
    db.session.flush()

    add_pace_tiers(route.id, [
        (60,   7.0, 7.0, 7.0),
        (180,  7.5, 7.5, 7.5),
        (300,  8.0, 8.0, 8.0),
        (420,  8.5, 8.5, 8.5),
        (540,  9.0, 9.0, 9.0),
        (None, 9.5, 9.5, 9.5),
    ])

    legs: list[Leg] = []
    for i in range(14, 28):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(route.id, len(legs) + 1, loc,
                      distance_km=safe_float(row[4]),
                      ascent_m=safe_float(row[5]),
                      descent_m=safe_float(row[6]),
                      notes=row[11].strip() if len(row) > 11 else '')
        legs.append(leg)
        if loc == 'Youth Hostel' and len(legs) > 1:
            break

    fw_mins = [round_min(parse_minutes(rows[14 + j][28])) if len(rows[14 + j]) > 28 else None
               for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, fw_mins)
    print(f'Lochaber Traverse: {len(legs)} legs, 1 attempt')


def import_mamores() -> None:
    rows = read_csv('mamores.csv')
    route = Route(name='Mamores', latitude=56.83, longitude=-5.10,
                  start_time='08:00', start_date='2026-06-01')
    db.session.add(route)
    db.session.flush()

    add_pace_tiers(route.id, [
        (60,   5.0, 5.0, 5.0),
        (180,  5.25, 5.25, 5.25),
        (300,  5.5, 5.5, 5.5),
        (420,  5.75, 5.75, 5.75),
        (540,  6.0, 6.0, 6.0),
        (None, 6.5, 6.5, 6.5),
    ])

    legs: list[Leg] = []
    for i in range(14, 28):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(route.id, len(legs) + 1, loc,
                      distance_km=safe_float(row[4]),
                      ascent_m=safe_float(row[5]),
                      descent_m=safe_float(row[6]),
                      notes=row[11].strip() if len(row) > 11 else '')
        legs.append(leg)

    fw_mins = [round_min(parse_minutes(rows[14 + j][36])) if len(rows[14 + j]) > 36 else None
               for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, fw_mins)
    print(f'Mamores: {len(legs)} legs, 1 attempt')


def import_mullardoch() -> None:
    rows = read_csv('mullardoch.csv')
    route = Route(name='Mullardoch Round', latitude=57.30, longitude=-5.15,
                  start_time='05:00', start_date='2026-03-23')
    db.session.add(route)
    db.session.flush()

    add_pace_tiers(route.id, [
        (60,   6.5, 6.5, 6.5),
        (180,  7.0, 7.0, 7.0),
        (300,  7.5, 7.5, 7.5),
        (420,  8.0, 8.0, 8.0),
        (540,  8.5, 8.5, 8.5),
        (None, 9.0, 9.0, 9.0),
    ])

    legs: list[Leg] = []
    for i in range(14, 28):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(route.id, len(legs) + 1, loc,
                      distance_km=safe_float(row[1]),
                      ascent_m=safe_float(row[2]),
                      descent_m=safe_float(row[3]),
                      notes=row[8].strip() if len(row) > 8 else '')
        legs.append(leg)
        if loc == 'Dam' and len(legs) > 1:
            break

    fw_mins = [round_min(parse_minutes(rows[14 + j][27])) if len(rows[14 + j]) > 27 else None
               for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, fw_mins)
    print(f'Mullardoch Round: {len(legs)} legs, 1 attempt')


def import_shiel() -> None:
    rows = read_csv('shiel.csv')
    route = Route(name='Shiel Round', latitude=57.22, longitude=-5.41,
                  start_time='07:00', start_date='2026-05-05')
    db.session.add(route)
    db.session.flush()

    add_pace_tiers(route.id, [
        (60,   6.0, 6.0, 6.0),
        (180,  6.5, 6.5, 6.5),
        (300,  7.0, 7.0, 7.0),
        (420,  7.5, 7.5, 7.5),
        (540,  8.0, 8.0, 8.0),
        (None, 8.5, 8.5, 8.5),
    ])

    legs: list[Leg] = []
    for i in range(14, 35):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(route.id, len(legs) + 1, loc,
                      distance_km=safe_float(row[4]),
                      ascent_m=safe_float(row[5]),
                      descent_m=safe_float(row[6]),
                      notes=row[11].strip() if len(row) > 11 else '')
        legs.append(leg)
        if loc == 'Cluanie' and len(legs) > 1:
            break

    fw_mins = [round_min(parse_minutes(rows[14 + j][26])) if len(rows[14 + j]) > 26 else None
               for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, fw_mins)
    print(f'Shiel Round: {len(legs)} legs, 1 attempt')


def import_assynt() -> None:
    rows = read_csv('assynt traverse.csv')
    route = Route(name='Assynt Traverse', latitude=58.15, longitude=-5.10,
                  start_time='06:00', start_date='2026-06-01')
    db.session.add(route)
    db.session.flush()

    add_pace_tiers(route.id, [
        (60,   7.0, 7.0, 7.0),
        (180,  7.5, 7.5, 7.5),
        (300,  8.0, 8.0, 8.0),
        (420,  8.5, 8.5, 8.5),
        (540,  9.0, 9.0, 9.0),
        (None, 9.5, 9.5, 9.5),
    ])

    legs: list[Leg] = []
    for i in range(14, 27):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(route.id, len(legs) + 1, loc,
                      distance_km=safe_float(row[4]),
                      ascent_m=safe_float(row[5]),
                      descent_m=safe_float(row[6]),
                      notes=row[11].strip() if len(row) > 11 else '')
        legs.append(leg)
        if loc == 'Quinag car park' and len(legs) > 1:
            break

    # No FW attempt exists for Assynt
    print(f'Assynt Traverse: {len(legs)} legs, 0 attempts')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if os.path.exists(TEMPLATE_DB):
        os.remove(TEMPLATE_DB)
        print(f'Removed existing {TEMPLATE_DB}')

    with app.app_context():
        db.create_all()

        import_munros()
        import_corbetts()
        import_wainwrights()

        import_ramsay()
        import_tranters()
        import_lochaber()
        import_mamores()
        import_mullardoch()
        import_shiel()
        import_assynt()

        db.session.commit()

    print(f'\nDone — {TEMPLATE_DB}')
