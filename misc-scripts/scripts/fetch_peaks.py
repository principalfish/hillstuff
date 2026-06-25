"""
Fetch peaks from OpenStreetMap via the Overpass API.

Usage:
    pip install requests
    python scripts/fetch_peaks.py --bbox S,W,N,E [options] [output.csv]

Examples:
    # Pyrenees
    python scripts/fetch_peaks.py --bbox 42.0,-2.0,43.5,3.5 --output csv/pyrenees_peaks.csv

    # Eastern Kyrgyzstan (Tian Shan)
    python scripts/fetch_peaks.py --bbox 39.0,74.0,43.0,81.0 --name-langs en,ru,ky --output csv/kyrgyzstan_peaks.csv

    # Western Kyrgyzstan (Fergana/Chatkal/Talas)
    python scripts/fetch_peaks.py --bbox 39.0,69.0,43.0,74.0 --name-langs en,ru,ky --output csv/kyrgyzstan_peaks_west.csv
"""

import argparse
import csv
from pathlib import Path

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Custom User-Agent avoids 406 from overpass-api.de with the default requests UA.
HEADERS = {"User-Agent": "hillstuff-peaks/1.0 (personal hill-running data)"}

SCRIPT_DIR = Path(__file__).parent


def build_query(bbox: tuple[float, float, float, float], min_ele: int) -> str:
    south, west, north, east = bbox
    return """
[out:json][timeout:120];
(
  node["natural"="peak"]["ele"](if: number(t["ele"]) >= {min_ele})({south},{west},{north},{east});
  way["natural"="peak"]["ele"](if: number(t["ele"]) >= {min_ele})({south},{west},{north},{east});
  relation["natural"="peak"]["ele"](if: number(t["ele"]) >= {min_ele})({south},{west},{north},{east});
);
out center tags;
""".format(south=south, west=west, north=north, east=east, min_ele=min_ele)


def fetch_peaks(bbox: tuple[float, float, float, float], min_ele: int) -> list[dict]:
    query = build_query(bbox, min_ele)
    print("Querying Overpass API...")
    resp = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    elements = data.get("elements", [])
    print(f"  {len(elements)} elements returned")
    return elements


def parse_element(el: dict, name_langs: list[str]) -> dict | None:
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

    # Build preferred name: try each language code in order, fall back to generic name.
    name = ""
    for lang in name_langs:
        candidate = tags.get(f"name:{lang}", "")
        if candidate:
            name = candidate
            break
    if not name:
        name = tags.get("name", "")

    # Always emit name columns for common languages present in the data.
    row: dict = {
        "osm_type": el["type"],
        "osm_id": el["id"],
        "name": name,
        "elevation_m": tags.get("ele", ""),
        "lat": lat,
        "lon": lon,
        "prominence": tags.get("prominence", ""),
        "wikidata": tags.get("wikidata", ""),
        "wikipedia": tags.get("wikipedia", ""),
    }
    # Emit name_XX columns for each requested language.
    for lang in name_langs:
        row[f"name_{lang}"] = tags.get(f"name:{lang}", "")

    return row


def _float(val: object) -> float:
    try:
        return float(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0.0


def write_csv(peaks: list[dict], path: str) -> None:
    if not peaks:
        print("No peaks to write.")
        return
    fieldnames = list(peaks[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(peaks)
    print(f"Written {len(peaks)} peaks to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch natural=peak nodes from Overpass API for a bounding box.",
    )
    parser.add_argument(
        "--bbox",
        required=True,
        metavar="S,W,N,E",
        help="Bounding box as south,west,north,east (float degrees, e.g. 42.0,-2.0,43.5,3.5)",
    )
    parser.add_argument(
        "--min-prominence",
        type=int,
        default=200,
        metavar="M",
        help="Drop peaks whose OSM prominence tag is set and below this value (default 200)",
    )
    parser.add_argument(
        "--min-elevation",
        type=int,
        default=500,
        metavar="M",
        help="Server-side elevation floor passed to Overpass (default 500)",
    )
    parser.add_argument(
        "--name-langs",
        default="en",
        metavar="LANGS",
        help="Comma-separated language codes for name fallback, e.g. en,ru,ky (default: en)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output CSV path (default: csv/peaks_<bbox>.csv relative to misc-scripts/)",
    )
    args = parser.parse_args()

    try:
        s, w, n, e = (float(x) for x in args.bbox.split(","))
    except ValueError:
        parser.error("--bbox must be four comma-separated floats: S,W,N,E")

    bbox = (s, w, n, e)
    name_langs = [lang.strip() for lang in args.name_langs.split(",") if lang.strip()]

    default_output = str(
        SCRIPT_DIR.parent / "csv" / f"peaks_{s}_{w}_{n}_{e}.csv"
    )
    output_path = args.output or default_output

    elements = fetch_peaks(bbox, args.min_elevation)

    peaks = []
    for el in elements:
        parsed = parse_element(el, name_langs)
        if parsed is not None:
            peaks.append(parsed)

    peaks.sort(key=lambda p: -_float(p["elevation_m"]))

    before = len(peaks)
    peaks = [
        p for p in peaks
        if not p["prominence"] or _float(p["prominence"]) >= args.min_prominence
    ]
    print(
        f"  {before} total → {len(peaks)} after filtering "
        f"(ele ≥ {args.min_elevation}m, prominence ≥ {args.min_prominence}m or untagged)"
    )

    if peaks:
        print("\nTop 10 peaks by elevation:")
        for p in peaks[:10]:
            nm = p["name"] or "(unnamed)"
            ele = p["elevation_m"] or "?"
            print(f"  {nm:40s}  {ele}m")

    write_csv(peaks, output_path)


if __name__ == "__main__":
    main()
