"""Import Shiel Round route from shiel.csv.

Header row 13 (0-indexed):
  0:Where, 1:Hours, 2:Time of day, 3:gap, 4:Dist, 5:Asc, 6:Desc
  11:Notes
Attempts: col 19 = Actual mins (per-leg), col 26 = FW Mins
Legs: rows 14-34
"""
from import_helpers import (
    get_app_context, delete_route, create_route, add_pace_tiers,
    add_leg, add_attempt, safe_float, parse_minutes, read_csv, db,
)

rows = read_csv('shiel.csv')

with get_app_context():
    delete_route('Shiel Round')

    route = create_route('Shiel Round', 57.22, -5.41, '07:00', '2026-05-05')
    add_pace_tiers(route.id, [
        (360, 6.5, 6.5, 6.5),
        (540, 7.0, 7.0, 7.0),
        (None, 7.5, 7.5, 7.5),
    ])

    legs = []
    for i in range(14, 35):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(
            route.id, len(legs) + 1, loc,
            distance_km=safe_float(row[4]),
            ascent_m=safe_float(row[5]),
            descent_m=safe_float(row[6]),
            notes=row[11].strip() if len(row) > 11 else '',
        )
        legs.append(leg)
        if loc == 'Cluanie' and len(legs) > 1:
            break

    def round_min(val: float | None) -> float | None:
        return round(val) if val is not None else None

    # My attempt - col 19
    mins = [round_min(parse_minutes(rows[14 + j][19])) if len(rows[14 + j]) > 19 else None
            for j in range(len(legs))]
    add_attempt(route.id, 'May 2024', '2024-05-05', legs, mins)

    # Finlay Wild attempt - col 26
    fw_mins = [round_min(parse_minutes(rows[14 + j][26])) if len(rows[14 + j]) > 26 else None
               for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, fw_mins)

    db.session.commit()
    print(f'Shiel Round: {len(legs)} legs, 2 attempts')
