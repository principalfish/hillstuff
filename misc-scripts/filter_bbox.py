"""
Filter a peaks CSV to a lat/lon bounding box.

Usage:
    python3 filter_bbox.py <lat_min> <lat_max> <lon_min> <lon_max> [input.csv [output.csv]]

Example:
    python3 filter_bbox.py 42.3 43.2 -1.0 2.8
"""

import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

args = sys.argv[1:]
if len(args) < 4:
    sys.exit(__doc__)

lat_min, lat_max, lon_min, lon_max = (float(a) for a in args[:4])
input_path  = Path(args[4]) if len(args) > 4 else SCRIPT_DIR / "merged_pyrenees_prom_195.csv"
output_path = Path(args[5]) if len(args) > 5 else input_path.with_stem(input_path.stem + "_bbox")

rows = list(csv.DictReader(open(input_path, encoding="utf-8")))

filtered = []
for r in rows:
    try:
        lat = float(r["lat"])
        lon = float(r["lon"])
    except (ValueError, KeyError):
        continue
    if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
        filtered.append(r)

with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(filtered)

print(f"Bbox: {lat_min}–{lat_max}°N, {lon_min}–{lon_max}°E")
print(f"{len(rows)} → {len(filtered)} peaks written to {output_path.name}")
