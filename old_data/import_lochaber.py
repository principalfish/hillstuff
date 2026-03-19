"""Import Lochaber Traverse route from lochaber_traverse.csv.

Header row 13 (0-indexed):
  0:Where, 1:Hours, 2:Time of day, 3:Total Hours, 4:Dist, 5:Asc, 6:Desc
  11:Notes
No actual attempts.
Legs: rows 14-27
"""
from import_helpers import (
    get_app_context, delete_route, create_route, add_pace_tiers,
    add_leg, add_attempt, safe_float, parse_minutes, read_csv, db,
)

rows = read_csv('lochaber_traverse.csv')

with get_app_context():
    delete_route('Lochaber Traverse')

    route = create_route('Lochaber Traverse', 56.83, -5.10, '05:00', '2026-09-02')
    add_pace_tiers(route.id, [
        (60, 7.0, 7.0, 7.0),
        (180, 7.5, 7.5, 7.5),
        (300, 8.0, 8.0, 8.0),
        (None, 8.5, 8.5, 8.5),
    ])

    legs = []
    for i in range(14, 28):
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
        if loc == 'Youth Hostel' and len(legs) > 1:
            break

    # Finlay Wild attempt - FW Mins at col 28
    def round_min(val: float | None) -> float | None:
        return round(val) if val is not None else None
    mins = [round_min(parse_minutes(rows[14 + j][28])) if len(rows[14 + j]) > 28 else None
            for j in range(len(legs))]
    add_attempt(route.id, 'Finlay Wild', None, legs, mins)

    db.session.commit()
    print(f'Lochaber Traverse: {len(legs)} legs, 1 attempt')
