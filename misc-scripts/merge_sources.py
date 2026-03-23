"""
Merge Ferranti and OSM peaks CSVs, deduplicating by proximity.

Ferranti is treated as authoritative — where both sources have the same peak,
the Ferranti record is kept but enriched with OSM's wikipedia/wikidata/names
if Ferranti lacks them.

OSM-only peaks (no Ferranti peak within DEDUP_RADIUS_M) are appended.

Usage:
    python merge_sources.py [output.csv]
    python merge_sources.py ferranti_pyrenees.csv 200m.csv merged.csv
"""

import csv
import math
import sys

FERRANTI_FILE = "ferranti_pyrenees.csv"
OSM_FILE      = "200m.csv"
BASQUE_FILE   = "basque_peaks.csv"
OUTPUT_FILE   = sys.argv[1] if len(sys.argv) > 1 else "merged_pyrenees.csv"

DEDUP_RADIUS_M = 750  # peaks within this distance are considered the same

FIELDNAMES = [
    "source", "osm_type", "osm_id", "name", "name_en", "name_fr", "name_es",
    "elevation_m", "lat", "lon", "prominence", "wikidata", "wikipedia",
]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two lat/lon points."""
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load(path: str, source: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["source"] = source
        r.setdefault("osm_type", "")
        r.setdefault("osm_id", "")
        r.setdefault("name_en", "")
        r.setdefault("name_fr", "")
        r.setdefault("name_es", "")
        r.setdefault("wikidata", "")
        r.setdefault("wikipedia", "")
    return rows


def coords(p: dict) -> tuple[float, float]:
    return float(p["lat"]), float(p["lon"])


ferranti = load(FERRANTI_FILE, "ferranti")
osm      = load(OSM_FILE, "osm")
basque   = load(BASQUE_FILE, "basque")

print(f"Ferranti: {len(ferranti)} peaks")
print(f"OSM:      {len(osm)} peaks")
print(f"Basque:   {len(basque)} peaks")


def dedup_into(authority: list[dict], candidates: list[dict], matched_ids: set[int]) -> None:
    """Merge candidates into authority, enriching authority records where they match."""
    for fp in authority:
        flat, flon = coords(fp)
        best_dist, best_match = float("inf"), None
        for i, cp in enumerate(candidates):
            if i in matched_ids:
                continue
            try:
                d = haversine(flat, flon, *coords(cp))
            except (ValueError, TypeError):
                continue
            if d < best_dist:
                best_dist, best_match = d, (i, cp)
        if best_match and best_dist <= DEDUP_RADIUS_M:
            idx, cp = best_match
            matched_ids.add(idx)
            for field in ("name_en", "name_fr", "name_es", "wikidata", "wikipedia", "osm_type", "osm_id"):
                if not fp.get(field) and cp.get(field):
                    fp[field] = cp[field]
            fp["source"] = fp["source"] + "+" + cp["source"].split("+")[0]


# Priority: ferranti > osm > basque
matched_osm: set[int] = set()
matched_basque: set[int] = set()

dedup_into(ferranti, osm, matched_osm)
dedup_into(ferranti, basque, matched_basque)

osm_only = [p for i, p in enumerate(osm) if i not in matched_osm]
dedup_into(osm_only, basque, matched_basque)

basque_only = [p for i, p in enumerate(basque) if i not in matched_basque]

MIN_ELEVATION_M = 750

merged = [p for p in ferranti + osm_only + basque_only
          if (float(p["elevation_m"]) if p.get("elevation_m") else 0) >= MIN_ELEVATION_M]

# Sort by elevation descending
merged.sort(key=lambda p: -(float(p["elevation_m"]) if p.get("elevation_m") else 0))

# Stats
sources: dict[str, int] = {}
for p in merged:
    sources[p["source"]] = sources.get(p["source"], 0) + 1
print(f"\nMerged: {len(merged)} peaks")
for s, n in sorted(sources.items()):
    print(f"  {s}: {n}")
print(f"  Basque-only added: {len(basque_only)}")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(merged)

print(f"\nWritten to {OUTPUT_FILE}")
