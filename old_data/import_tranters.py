"""Import Tranter's Round route from tranters.csv.

Header row 13 (0-indexed, but row 12 has grouping header):
  0:Where, 1:Dist, 2:Asc, 3:Desc, 4:gap, 5:Cum Dist, 6:Cum Asc, 7:Cum Desc, 8:Notes
Attempts: col 21=Estimate mins, col 22=Actual mins (Tranter 2024), col 36=Tranter 2024 mins again
  Actually: col 22 = actual mins for unnamed effort, col 36 = Tranter 2024 mins
  FW: col 30 = FW mins
Legs: rows 14-34

Let me recheck the header:
Row 12: ,,,,,Cumulative,,,,,,,,,,,,,,,Estimate,Actual,,,,,,,,,,,,,Tranter 2024,...
Row 13: Where,Dist,Asc,Desc,,Dist,Asc,Desc,Notes,Time at water,,Effort,Min/effort,Mins,,Hours,,Time of day,,,Mins,Mins,Diff,Cumulative,Hours,,Cumulative,Min/unit,,FW Mins,Diff,Ratio,,,Mins,Cumulative,...

So actual attempt data:
- Col 21 = Estimate Mins
- Col 22 = Actual Mins (this is the real attempt)
- Col 30 = FW Mins
- Col 36 = Tranter 2024 Mins
"""
from import_helpers import (
    get_app_context, delete_route, create_route, add_pace_tiers,
    add_leg, add_attempt, safe_float, parse_minutes, read_csv, db,
)

rows = read_csv('tranters.csv')

with get_app_context():
    delete_route("Tranter's Round")

    route = create_route("Tranter's Round", 56.83, -5.10, '02:00', '2026-06-01')
    add_pace_tiers(route.id, [
        (540, 6.5, 6.5, 6.5),
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
            distance_km=safe_float(row[1]),
            ascent_m=safe_float(row[2]),
            descent_m=safe_float(row[3]),
            notes=row[8].strip() if len(row) > 8 else '',
        )
        legs.append(leg)
        if loc == 'Youth Hostel' and len(legs) > 1:
            break

    def round_min(val: float | None) -> float | None:
        return round(val) if val is not None else None

    # Attempts: col 21 = Jun 2022, col 29 = FW, col 34 = Tranter 2024
    for name, date, col in [
        ('June 2022', '2022-06-01', 21),
        ('June 2024', '2024-06-01', 34),
        ('Finlay Wild', None, 29),
    ]:
        mins = [round_min(parse_minutes(rows[14 + j][col])) if len(rows[14 + j]) > col else None
                for j in range(len(legs))]
        add_attempt(route.id, name, date, legs, mins)

    db.session.commit()
    print(f"Tranter's Round: {len(legs)} legs, 3 attempts")
