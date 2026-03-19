"""Import Ramsay's Round route from ramsay.csv.

Header row 13 (0-indexed):
  0:Where, 1:Hours, 2:Time of day, 3:Total Hours, 4:Dist, 5:Asc, 6:Desc
  11:Notes, 12:Water
Attempts: col 23=Ramsay 2023 mins, col 32=Tranter 2024 mins, col 46=Ramsay 2025 mins
Legs: rows 14-43
"""
from import_helpers import (
    get_app_context, delete_route, create_route, add_pace_tiers,
    add_leg, add_attempt, safe_float, parse_minutes, read_csv, db,
)

rows = read_csv('ramsay.csv')

with get_app_context():
    delete_route("Ramsay's Round")

    route = create_route("Ramsay's Round", 56.83, -5.10, '00:00', '2026-07-11')
    add_pace_tiers(route.id, [
        (60, 6.0, 6.0, 6.0),
        (180, 6.5, 6.5, 6.5),
        (240, 7.0, 7.0, 7.0),
        (300, 7.5, 7.5, 7.5),
        (540, 8.0, 8.0, 8.0),
        (None, 8.5, 8.5, 8.5),
    ])

    legs = []
    for i in range(14, 44):
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

    def round_min(val: float | None) -> float | None:
        return round(val) if val is not None else None

    # Attempts: col 22 = Ramsay 2023 per-leg, col 42 = FW per-leg, col 45 = Ramsay 2025 per-leg
    for name, date, col in [
        ('Ramsay 2023', '2023-07-01', 22),
        ('Ramsay 2025', '2025-07-01', 45),
        ('Finlay Wild', None, 42),
    ]:
        mins = [round_min(parse_minutes(rows[14 + j][col])) if len(rows[14 + j]) > col else None
                for j in range(len(legs))]
        add_attempt(route.id, name, date, legs, mins)

    db.session.commit()
    print(f"Ramsay's Round: {len(legs)} legs, 3 attempts")
