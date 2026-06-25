"""
calc_prominence.py — Compute topographic prominence for peaks in a bounding box.

Uses Copernicus GLO-30 (~30m) DEM tiles from the public AWS S3 bucket and a
cell-sort union-find algorithm to find the key col (highest saddle to higher
terrain) for each peak.

Usage:
    pip install numpy requests rasterio
    python scripts/calc_prominence.py --input csv/<region>_peaks.csv [options]

By default the DEM tile bbox is derived from the input CSV's peak extent
(floored/ceiled to whole tiles, plus --pad degrees). Pass --bbox to set it
explicitly — e.g. to constrain the extent and limit download/RAM.

Examples:
    # Pyrenees — bbox auto-derived from the peaks
    python scripts/calc_prominence.py \\
        --input csv/pyrenees_peaks.csv \\
        --output csv/pyrenees_prom.csv

    # Eastern Kyrgyzstan — explicit bbox, trim to >= 200 m
    python scripts/calc_prominence.py \\
        --bbox 39,74,43,81 \\
        --input csv/kyrgyzstan_peaks.csv \\
        --output csv/kyrgyzstan_prom.csv \\
        --min-prominence 200

    # Western Kyrgyzstan — auto bbox with a little padding
    python scripts/calc_prominence.py \\
        --input csv/kyrgyzstan_peaks_west.csv \\
        --output csv/kyrgyzstan_prom_west.csv \\
        --pad 0.5 --min-prominence 200

Tiles are downloaded automatically and cached in
misc-scripts/dem_cache_<lat_min>_<lon_min>_<lat_max>_<lon_max>/ by default.
Use --cache-dir to override.

Bbox note: tile bounds are INTEGER degrees — one Copernicus tile per lat/lon
degree. When deriving, a peak's key col may fall just outside a tight extent
(reported as no prominence / unbounded); raise --pad to extend the box.
"""

import argparse
import csv
import math
import sys
import time
from pathlib import Path

import numpy as np
import requests

try:
    import rasterio
except ImportError:
    sys.exit("rasterio required:  pip install rasterio")

SCRIPT_DIR = Path(__file__).parent

COP_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
NODATA   = -32768


# ---------------------------------------------------------------------------
# Tile helpers
# ---------------------------------------------------------------------------

def cop_tile_key(lat: int, lon: int) -> str:
    """Copernicus tile stem (directory name and .tif filename)."""
    ns = f"N{lat:02d}"      if lat >= 0 else f"S{abs(lat):02d}"
    ew = f"E{abs(lon):03d}" if lon >= 0 else f"W{abs(lon):03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def cop_tile_url(lat: int, lon: int) -> str:
    key = cop_tile_key(lat, lon)
    return f"{COP_BASE}/{key}/{key}.tif"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_tiles(
    cache_dir: Path,
    lat_min: int, lat_max: int,
    lon_min: int, lon_max: int,
) -> None:
    """Download Copernicus COG tiles for the bounding box."""
    cache_dir.mkdir(exist_ok=True)
    total = (lat_max - lat_min) * (lon_max - lon_min)
    done = 0
    for lat in range(lat_min, lat_max):
        for lon in range(lon_min, lon_max):
            done += 1
            out = cache_dir / f"{cop_tile_key(lat, lon)}.tif"
            if out.exists():
                print(f"  [{done}/{total}] {out.name[:40]}… cached")
                continue
            url = cop_tile_url(lat, lon)
            print(f"  [{done}/{total}] GET {url}")
            resp = requests.get(url, timeout=180, stream=True)
            if resp.status_code == 404:
                print(f"    not found (ocean/no-data tile) — skipping")
                continue
            resp.raise_for_status()
            size = 0
            with open(out, "wb") as fh:
                for chunk in resp.iter_content(65536):
                    fh.write(chunk)
                    size += len(chunk)
            print(f"    Saved ({size // 1_048_576} MB)")


# ---------------------------------------------------------------------------
# Load DEM
# ---------------------------------------------------------------------------

def load_tif(path: Path) -> np.ndarray:
    """Read a Copernicus COG tile as int16, replacing nodata with NODATA."""
    with rasterio.open(path) as ds:
        data = ds.read(1).astype(np.float32)
        nd_value = ds.nodata
    if nd_value is not None:
        data[data == nd_value] = NODATA
    data[data < -9000] = NODATA
    return data.astype(np.int16)


def load_dem(
    cache_dir: Path,
    lat_min: int, lat_max: int,
    lon_min: int, lon_max: int,
) -> tuple[np.ndarray, tuple[float, float, float]]:
    """
    Stitch Copernicus tiles into a single array.

    Copernicus tiles have shared edges removed, so each tile slots in cleanly
    with no deduplication.

    Returns:
        dem           int16 array, shape (nrows, ncols)
        geotransform  (north_lat, west_lon, cell_deg)
    """
    tile_h = tile_w = 0
    for lat in range(lat_min, lat_max):
        for lon in range(lon_min, lon_max):
            p = cache_dir / f"{cop_tile_key(lat, lon)}.tif"
            if p.exists():
                with rasterio.open(p) as ds:
                    tile_h, tile_w = ds.height, ds.width
                break
        if tile_h:
            break
    if not tile_h:
        sys.exit("No tiles found in cache — run download first.")

    cell_deg = 1.0 / tile_h
    n_lat    = lat_max - lat_min
    n_lon    = lon_max - lon_min
    nrows    = n_lat * tile_h
    ncols    = n_lon * tile_w

    print(f"  Allocating DEM array: {nrows}×{ncols} = {nrows*ncols:,} cells "
          f"({nrows*ncols*2/1e9:.1f} GB int16)…")
    dem = np.full((nrows, ncols), NODATA, dtype=np.int16)

    for lat in range(lat_min, lat_max):
        for lon in range(lon_min, lon_max):
            tpath = cache_dir / f"{cop_tile_key(lat, lon)}.tif"
            if not tpath.exists():
                print(f"  WARNING: {tpath.name} not found — leaving NODATA")
                continue
            tile = load_tif(tpath)
            row0 = (lat_max - 1 - lat) * tile_h
            col0 = (lon - lon_min) * tile_w
            dem[row0:row0 + tile_h, col0:col0 + tile_w] = tile

    gt = (float(lat_max), float(lon_min), cell_deg)
    return dem, gt


def latlon_to_rc(
    lat: float, lon: float,
    gt: tuple[float, float, float],
) -> tuple[int, int]:
    north, west, cell = gt
    return round((north - lat) / cell), round((lon - west) / cell)


# ---------------------------------------------------------------------------
# Prominence — cell-sort union-find
# ---------------------------------------------------------------------------

def compute_prominence(
    dem: np.ndarray,
    peaks: list[tuple[int, int, int, float]],  # (idx, row, col, elev)
) -> dict[int, int]:
    """
    Cell-sort prominence algorithm (memory-efficient alternative to Kruskal).

    Sort all DEM cells by elevation descending, then process each cell by
    unioning it with any already-processed neighbours.  When two components
    with different dominant peaks merge, record the saddle as the key col
    for the lower-elevation peak.

    Returns dict: peak_idx -> key_col_elevation (int, metres).
    """
    nrows, ncols = dem.shape
    n = nrows * ncols

    t0 = time.time()
    print(f"  Sorting {nrows}×{ncols} = {n:,} cells by elevation…")

    flat = dem.ravel().astype(np.int32)
    flat[flat == NODATA] = -32767

    # argsort returns int64; cast to int32 immediately to halve memory
    sorted_idx   = np.argsort(flat)[::-1]
    sorted_cells = sorted_idx.astype(np.int32)
    del sorted_idx

    print(f"  Building union-find arrays… ({time.time()-t0:.1f}s)")
    parent   = np.arange(n, dtype=np.int32)
    dom_peak = np.full(n, -1,     dtype=np.int32)
    dom_elev = np.full(n, -32767, dtype=np.int32)

    for peak_idx, row, col, elev in peaks:
        cell = row * ncols + col
        dom_peak[cell] = peak_idx
        dom_elev[cell] = int(elev)

    processed = np.zeros(n, dtype=bool)
    key_col: dict[int, int] = {}

    def find(i: int) -> int:
        while parent.item(i) != i:
            parent[i] = parent.item(parent.item(i))   # path halving
            i = parent.item(i)
        return i

    def union(a: int, b: int, w: int) -> None:
        ra = find(a);  rb = find(b)
        if ra == rb:
            return
        da = dom_peak.item(ra);  db = dom_peak.item(rb)
        ea = dom_elev.item(ra);  eb = dom_elev.item(rb)
        if da >= 0 and db >= 0 and da != db:
            if ea < eb:
                if da not in key_col:
                    key_col[da] = w
            elif eb < ea:
                if db not in key_col:
                    key_col[db] = w
        if ea >= eb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    print(f"  Running union-find… ({time.time()-t0:.1f}s)")
    report_every = max(1, n // 40)

    for ci in range(n):
        if ci % report_every == 0:
            print(f"    {ci*100//n:3d}%  {ci:>12,}/{n:,}  "
                  f"{time.time()-t0:5.0f}s", end="\r")

        cell = sorted_cells.item(ci)
        elev = flat.item(cell)
        if elev <= -32000:
            continue

        processed[cell] = True
        r = cell // ncols
        c = cell  % ncols

        if r > 0           and processed.item(cell - ncols): union(cell, cell - ncols, elev)
        if r < nrows - 1   and processed.item(cell + ncols): union(cell, cell + ncols, elev)
        if c > 0           and processed.item(cell - 1):     union(cell, cell - 1,     elev)
        if c < ncols - 1   and processed.item(cell + 1):     union(cell, cell + 1,     elev)

    print(f"\n  Done  ({time.time()-t0:.0f}s)")
    return key_col


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _in_bbox(
    row: dict,
    lat_min: int, lat_max: int,
    lon_min: int, lon_max: int,
) -> bool:
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
    except (ValueError, KeyError):
        return False
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def derive_bbox(rows: list[dict], pad: float) -> tuple[int, int, int, int]:
    """
    Derive integer tile bounds covering all peaks in the CSV, plus `pad` degrees.

    Floors the south/west and ceils the north/east so the returned bounds line up
    with whole Copernicus tiles. Returns (lat_min, lon_min, lat_max, lon_max).
    """
    lats, lons = [], []
    for r in rows:
        try:
            lats.append(float(r["lat"]))
            lons.append(float(r["lon"]))
        except (ValueError, KeyError):
            continue
    if not lats:
        sys.exit("Cannot derive --bbox: no valid lat/lon found in input CSV.")

    lat_min = math.floor(min(lats) - pad)
    lat_max = math.ceil(max(lats) + pad)
    lon_min = math.floor(min(lons) - pad)
    lon_max = math.ceil(max(lons) + pad)

    # Upper bounds are exclusive in the tile range; guarantee at least one tile.
    lat_max = max(lat_max, lat_min + 1)
    lon_max = max(lon_max, lon_min + 1)
    return lat_min, lon_min, lat_max, lon_max


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute topographic prominence using Copernicus GLO-30 DEM tiles.",
    )
    parser.add_argument(
        "--bbox",
        default=None,
        metavar="LAT_MIN,LON_MIN,LAT_MAX,LON_MAX",
        help=(
            "Integer degree tile bounds, e.g. 42,-2,44,4. "
            "Optional — if omitted, derived from the input CSV's peak extent "
            "(floor/ceil to whole tiles) plus --pad. Pass this to constrain the "
            "extent (e.g. to limit download/RAM)."
        ),
    )
    parser.add_argument(
        "--pad",
        type=float,
        default=0.0,
        metavar="DEG",
        help=(
            "Degrees of padding added around the input extent when --bbox is "
            "derived (default 0). Increase if peaks sit near a tile edge and "
            "their key col may fall just outside."
        ),
    )
    parser.add_argument(
        "--input",
        default=None,
        metavar="FILE",
        help="Input peaks CSV (default: csv/peaks.csv relative to misc-scripts/)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output CSV path (default: input path with _prom suffix)",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        metavar="DIR",
        help="DEM tile cache directory (default: misc-scripts/dem_cache_<bbox>/)",
    )
    parser.add_argument(
        "--min-prominence",
        type=int,
        default=0,
        metavar="M",
        help=(
            "If > 0, trim output to peaks with computed prominence >= M "
            "(peaks with no key col found — effectively unbounded — are kept). "
            "Default 0 = no trimming."
        ),
    )
    args = parser.parse_args()

    # Input / output paths
    input_path = Path(args.input) if args.input else SCRIPT_DIR.parent / "csv" / "peaks.csv"
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_stem(input_path.stem + "_prom")

    # 1. Load peaks
    print(f"Loading peaks from {input_path}…")
    rows = load_rows(input_path)
    print(f"  {len(rows)} rows")

    # Resolve the tile bbox: explicit --bbox, or derived from the peak extent.
    if args.bbox:
        try:
            lat_min, lon_min, lat_max, lon_max = (int(x) for x in args.bbox.split(","))
        except ValueError:
            parser.error("--bbox must be four comma-separated integers: LAT_MIN,LON_MIN,LAT_MAX,LON_MAX")
        before = len(rows)
        rows = [r for r in rows if _in_bbox(r, lat_min, lat_max, lon_min, lon_max)]
        print(f"  {before} → {len(rows)} rows within --bbox "
              f"(lat {lat_min}–{lat_max}, lon {lon_min}–{lon_max})")
    else:
        lat_min, lon_min, lat_max, lon_max = derive_bbox(rows, args.pad)
        print(f"  Derived bbox from peak extent (pad {args.pad}°): "
              f"lat {lat_min}–{lat_max}, lon {lon_min}–{lon_max}")

    # Cache dir (named from the resolved bbox)
    cache_dir = (
        Path(args.cache_dir)
        if args.cache_dir
        else SCRIPT_DIR.parent / f"dem_cache_{lat_min}_{lon_min}_{lat_max}_{lon_max}"
    )

    tile_count = (lat_max - lat_min) * (lon_max - lon_min)
    cell_count  = tile_count * 3601 * 3601  # approximate
    print(f"Tiles: {tile_count}  (~{cell_count//1_000_000}M cells)")

    # 2. Download DEM tiles
    print(f"Downloading DEM tiles to {cache_dir}…")
    download_tiles(cache_dir, lat_min, lat_max, lon_min, lon_max)

    # 3. Stitch DEM
    print("Loading DEM…")
    dem, gt = load_dem(cache_dir, lat_min, lat_max, lon_min, lon_max)
    nrows, ncols = dem.shape
    print(f"  {nrows}×{ncols} = {nrows*ncols:,} cells  "
          f"({gt[0]}°N to {gt[0]-(nrows-1)*gt[2]:.1f}°N, "
          f"{gt[1]}°E to {gt[1]+(ncols-1)*gt[2]:.1f}°E)")

    # 4. Map peaks to DEM cells
    peaks: list[tuple[int, int, int, float]] = []
    skipped = 0
    for i, row in enumerate(rows):
        try:
            lat  = float(row["lat"])
            lon  = float(row["lon"])
            elev = float(row["elevation_m"])
        except (ValueError, KeyError):
            skipped += 1
            continue
        r, c = latlon_to_rc(lat, lon, gt)
        if not (0 <= r < nrows and 0 <= c < ncols):
            skipped += 1
            continue
        if dem[r, c] == NODATA:
            skipped += 1
            continue
        peaks.append((i, r, c, elev))

    print(f"  {len(peaks)} peaks mapped  ({skipped} skipped)")

    # 5. Compute prominence
    print("Computing prominence…")
    key_col = compute_prominence(dem, peaks)

    # 6. Report top results
    results: list[tuple[str, float, int | None, int, str]] = []
    for peak_idx, _r, _c, elev in peaks:
        kc   = key_col.get(peak_idx)
        prom = int(round(elev - kc)) if kc is not None else None
        name = rows[peak_idx].get("name") or "(unnamed)"
        orig = rows[peak_idx].get("prominence", "")
        results.append((name, elev, prom, peak_idx, orig))

    results.sort(key=lambda x: -(x[2] or -1))
    print(f"\n{'Peak':<40} {'Elev':>6}  {'Calc':>8}  {'CSV':>8}")
    print("-" * 68)
    for name, elev, prom, _pidx, orig in results[:20]:
        ps = f"{prom}m" if prom is not None else "n/a"
        print(f"  {name:<38} {elev:>6.0f}m  {ps:>8}  {orig:>8}")

    # 7. Annotate rows with computed prominence
    fieldnames = list(rows[0].keys()) if rows else []
    if "prominence_calc" not in fieldnames:
        fieldnames.append("prominence_calc")

    kc_lookup = {peak_idx: key_col.get(peak_idx) for peak_idx, *_ in peaks}
    for peak_idx, _r, _c, elev in peaks:
        kc = kc_lookup[peak_idx]
        rows[peak_idx]["prominence_calc"] = (
            int(round(elev - kc)) if kc is not None else ""
        )

    # 8. Optionally trim to peaks with computed prominence >= min_prominence.
    #    A blank prominence_calc means the peak is the high point of its area
    #    (no key col found within the bbox — effectively unbounded) or it
    #    couldn't be mapped to the DEM. Keep those; only drop peaks we can
    #    positively show are below the threshold.
    if args.min_prominence > 0:
        def _prom_ok(row: dict) -> bool:
            val = row.get("prominence_calc", "")
            if val == "" or val is None:
                return True
            return int(val) >= args.min_prominence

        before_trim = len(rows)
        rows = [r for r in rows if _prom_ok(r)]
        print(f"  Trimmed {before_trim} → {len(rows)} rows "
              f"(prominence_calc ≥ {args.min_prominence}m, plus unbounded/unmapped)")

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWritten {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
