"""Import Mullardoch Round route from mullardoch.csv.

Header row 13 (0-indexed, row 12 has grouping):
  0:Where, 1:Dist, 2:Asc, 3:Desc, 4:gap, 5:Cum Dist, 6:Cum Asc, 7:Cum Desc, 8:Notes
No actual attempts (only estimates).
Legs: rows 14-27
"""
from import_helpers import (
    get_app_context, delete_route, create_route, add_pace_tiers,
    add_leg, add_attempt, safe_float, parse_minutes, read_csv, db,
)

rows = read_csv('mullardoch.csv')

with get_app_context():
    delete_route('Mullardoch Round')

    route = create_route('Mullardoch Round', 57.30, -5.15, '05:00', '2026-03-23')
    add_pace_tiers(route.id, [
        (240, 6.5, 6.5, 6.5),
        (None, 7.0, 7.0, 7.0),
    ])

    legs = []
    for i in range(14, 28):
        row = rows[i]
        loc = row[0].strip()
        if not loc:
            break
        leg = add_leg(
            route.id, len(legs) + 1, loc,
            distance_km=safe_float(row[1]),
            ascent_m=safe_float(row[2]),
            descent_m=safe_float(row[3]),
            notes=row[8].strip() if len(row) > 8 else '',
        )
        legs.append(leg)
        if loc == 'Dam' and len(legs) > 1:
            break

    # Finlay Wild attempt - FW Mins at col 27
    def round_min(val: float | None) -> float | None:
        return round(val) if val is not None else None
    mins = [round_min(parse_minutes(rows[14 + j][27])) if len(rows[14 + j]) > 27 else None
            for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, mins)

    db.session.commit()
    print(f'Mullardoch Round: {len(legs)} legs, 1 attempt')
