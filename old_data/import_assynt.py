"""Import Assynt Traverse route from assynt traverse.csv.

Header row 13 (0-indexed):
  0:Where, 1:Hours, 2:Time of day, 3:Total hours, 4:Dist, 5:Asc, 6:Desc
  11:Notes
No actual attempts.
Legs: rows 14-26
"""
from import_helpers import (
    get_app_context, delete_route, create_route, add_pace_tiers,
    add_leg, safe_float, read_csv, db,
)

rows = read_csv('assynt traverse.csv')

with get_app_context():
    delete_route('Assynt Traverse')

    route = create_route('Assynt Traverse', 58.15, -5.10, '06:00', '2026-06-01')
    add_pace_tiers(route.id, [
        (600, 7.5, 7.5, 7.5),
        (None, 8.0, 8.0, 8.0),
    ])

    legs = []
    for i in range(14, 27):
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
        if loc == 'Quinag car park' and len(legs) > 1:
            break

    db.session.commit()
    print(f'Assynt Traverse: {len(legs)} legs, 0 attempts')
