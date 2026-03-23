"""
Fetch Kyrgyzstan peaks from OpenStreetMap via the Overpass API.

Usage:
    pip install requests
    python fetch_kyrgyzstan_peaks.py [output.csv]

Defaults to kyrgyzstan_peaks.csv.
"""

import argparse
import csv
import sys
import time

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box: eastern Kyrgyzstan — Bishkek area east to Chinese border.
# Matches the DEM bbox in calc_prominence_kyrgyzstan.py.
KYRGYZSTAN_BBOX = (39.0, 74.0, 43.0, 81.0)

OUTPUT_FILE = "kyrgyzstan_peaks.csv"
MIN_PROMINENCE_M = 200
MIN_ELEVATION_M = 500  # server-side floor

QUERY = """
[out:json][timeout:120];
(
  node["natural"="peak"]["ele"](if: number(t["ele"]) >= {min_ele})({south},{west},{north},{east});
  way["natural"="peak"]["ele"](if: number(t["ele"]) >= {min_ele})({south},{west},{north},{east});
  relation["natural"="peak"]["ele"](if: number(t["ele"]) >= {min_ele})({south},{west},{north},{east});
);
out center tags;
""".format(
    south=KYRGYZSTAN_BBOX[0],
    west=KYRGYZSTAN_BBOX[1],
    north=KYRGYZSTAN_BBOX[2],
    east=KYRGYZSTAN_BBOX[3],
    min_ele=MIN_ELEVATION_M,
)


def fetch_peaks() -> list[dict]:
    print("Querying Overpass API...")
    resp = requests.post(OVERPASS_URL, data={"data": QUERY}, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    elements = data.get("elements", [])
    print(f"  {len(elements)} elements returned")
    return elements


def parse_element(el: dict) -> dict | None:
    tags = el.get("tags", {})

    if el["type"] == "node":
        lat = el.get("lat")
        lon = el.get("lon")
    else:
        center = el.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None

    return {
        "osm_type": el["type"],
        "osm_id": el["id"],
        "name": (
            tags.get("name:en")
            or tags.get("name:ru")
            or tags.get("name:ky")
            or tags.get("name", "")
        ),
        "name_en": tags.get("name:en", ""),
        "name_ru": tags.get("name:ru", ""),
        "name_ky": tags.get("name:ky", ""),
        "elevation_m": tags.get("ele", ""),
        "lat": lat,
        "lon": lon,
        "prominence": tags.get("prominence", ""),
        "wikidata": tags.get("wikidata", ""),
        "wikipedia": tags.get("wikipedia", ""),
    }


def _float(val: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def write_csv(peaks: list[dict], path: str) -> None:
    if not peaks:
        print("No peaks to write.")
        return
    fieldnames = list(peaks[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(peaks)
    print(f"Written {len(peaks)} peaks to {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default=OUTPUT_FILE)
    args = parser.parse_args()

    elements = fetch_peaks()

    peaks = []
    for el in elements:
        parsed = parse_element(el)
        if parsed is not None:
            peaks.append(parsed)

    peaks.sort(key=lambda p: -_float(p["elevation_m"]))

    before = len(peaks)
    peaks = [
        p for p in peaks
        if not p["prominence"] or _float(p["prominence"]) >= MIN_PROMINENCE_M
    ]
    print(f"  {before} total -> {len(peaks)} after filtering "
          f"(ele >= {MIN_ELEVATION_M}m, prominence >= {MIN_PROMINENCE_M}m or untagged)")

    if peaks:
        print(f"\nTop 10 peaks by elevation:")
        for p in peaks[:10]:
            name = p["name"] or p["name_en"] or "(unnamed)"
            ele = p["elevation_m"] or "?"
            print(f"  {name:40s}  {ele}m")

    write_csv(peaks, args.output)


if __name__ == "__main__":
    main()
