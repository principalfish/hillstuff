"""Import Mamores route from mamores.csv.

Header row 13 (0-indexed):
  0:Where, 1:Hours, 2:Time of day, 3:gap, 4:Dist, 5:Asc, 6:Desc, ...
  11:Notes
Attempts: col 21=2025 mins, col 29=2024 mins, col 36=FW mins
Legs: rows 14-27 (Lower Falls start to Lower Falls end)
"""
from import_helpers import (
    get_app_context, delete_route, create_route, add_pace_tiers,
    add_leg, add_attempt, safe_float, parse_minutes, read_csv, db,
)

rows = read_csv('mamores.csv')

with get_app_context():
    delete_route('Mamores')

    route = create_route('Mamores', 56.83, -5.10, '08:00', '2026-06-01')
    add_pace_tiers(route.id, [
        (420, 5.25, 5.25, 5.25),
        (420, 5.5, 5.5, 5.5),
        (None, 6.0, 6.0, 6.0),
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

    def round_min(val: float | None) -> float | None:
        return round(val) if val is not None else None

    # Attempts: col 20 = 2025 per-leg, col 28 = 2024 per-leg, col 36 = FW per-leg
    for name, date, col in [
        ('2025', '2025-07-11', 20),
        ('2024', '2024-05-31', 28),
        ('Finlay Wild', None, 36),
    ]:
        mins = [round_min(parse_minutes(rows[14 + j][col])) if len(rows[14 + j]) > col else None
                for j in range(len(legs))]
        add_attempt(route.id, name, date, legs, mins)

    db.session.commit()
    print(f'Mamores: {len(legs)} legs, 3 attempts')
