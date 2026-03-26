"""
Fetches food shops in the Pyrenees from the Overpass API.
Bounding box is derived from peaks_filtered_195m.csv extremities + 10 km padding.
Saves to pyrenees_food_shops.csv in the same directory.

Usage:
    python fetch_pyrenees_food.py
"""

import csv
import json
import math
import os
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PEAKS_CSV  = os.path.join(SCRIPT_DIR, 'peaks_filtered_195m.csv')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'pyrenees_food_shops.csv')
PADDING_KM = 10

SHOP_TYPES = [
    'supermarket', 'convenience',  'greengrocer',
    'food',  'general', 'kiosk',
]

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
FIELDNAMES = ['name', 'lat', 'lon', 'shop', 'brand', 'opening_hours', 'website', 'phone']


def compute_bbox(csv_file: str, padding_km: float) -> str:
    lats: list[float] = []
    lons: list[float] = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                lats.append(float(row['lat']))
                lons.append(float(row['lon']))
            except (ValueError, KeyError):
                pass
    if not lats:
        raise ValueError(f'No lat/lon data found in {csv_file}')
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    mid_lat = (min_lat + max_lat) / 2
    pad_lat = padding_km / 111.0
    pad_lon = padding_km / (111.0 * math.cos(math.radians(mid_lat)))
    south = round(min_lat - pad_lat, 4)
    north = round(max_lat + pad_lat, 4)
    west  = round(min_lon - pad_lon, 4)
    east  = round(max_lon + pad_lon, 4)
    return f'{south},{west},{north},{east}'


def build_query(bbox: str) -> str:
    # Use exact-match union (index lookups) rather than regex — much faster on Overpass
    lines = []
    for shop in SHOP_TYPES:
        lines.append(f'  node["shop"="{shop}"]({bbox});')
        lines.append(f'  way["shop"="{shop}"]({bbox});')
    return '[out:json][timeout:180];\n(\n' + '\n'.join(lines) + '\n);\nout center;'


OVERPASS_MIRRORS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
]


def fetch_overpass(query: str) -> dict:  # type: ignore[type-arg]
    data = urllib.parse.urlencode({'data': query}).encode()
    last_err: Exception = Exception('no mirrors tried')
    for url in OVERPASS_MIRRORS:
        try:
            req = urllib.request.Request(url, data=data)
            req.add_header('User-Agent', 'hillstuff-misc/1.0')
            with urllib.request.urlopen(req, timeout=210) as resp:
                return json.loads(resp.read())  # type: ignore[no-any-return]
        except Exception as e:
            print(f'  {url} failed: {e}')
            last_err = e
    raise last_err


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def load_peak_coords(csv_file: str) -> list[tuple[float, float]]:
    peaks = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            try:
                peaks.append((float(row['lat']), float(row['lon'])))
            except (ValueError, KeyError):
                pass
    return peaks


def near_any_peak(lat: float, lon: float, peaks: list[tuple[float, float]], max_km: float) -> bool:
    return any(haversine_km(lat, lon, plat, plon) <= max_km for plat, plon in peaks)


def extract_rows(result: dict) -> list[dict]:  # type: ignore[type-arg]
    rows = []
    for el in result.get('elements', []):
        tags = el.get('tags', {})
        if el['type'] == 'node':
            lat = el.get('lat')
            lon = el.get('lon')
        elif el['type'] == 'way':
            center = el.get('center', {})
            lat = center.get('lat')
            lon = center.get('lon')
        else:
            continue
        if lat is None or lon is None:
            continue
        name = tags.get('name') or tags.get('name:en') or tags.get('name:fr') or tags.get('brand', '')
        rows.append({
            'name': name,
            'lat': lat,
            'lon': lon,
            'shop': tags.get('shop', ''),
            'brand': tags.get('brand', ''),
            'opening_hours': tags.get('opening_hours', ''),
            'website': tags.get('website', ''),
            'phone': tags.get('phone', ''),
        })
    return rows


def main() -> None:
    print(f'Loading peaks from {os.path.basename(PEAKS_CSV)} ...')
    peaks = load_peak_coords(PEAKS_CSV)
    print(f'  {len(peaks)} peaks loaded')

    print(f'Computing bbox + {PADDING_KM} km padding ...')
    bbox = compute_bbox(PEAKS_CSV, PADDING_KM)
    print(f'Bbox: {bbox}  (south,west,north,east)')

    print('Fetching from Overpass API (may take 30–60 s) ...')
    result = fetch_overpass(build_query(bbox))
    rows = extract_rows(result)
    print(f'Found {len(rows)} food shops in bbox')

    rows = [r for r in rows if near_any_peak(float(r['lat']), float(r['lon']), peaks, PADDING_KM)]
    print(f'  {len(rows)} within {PADDING_KM} km of a peak')

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved to {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
