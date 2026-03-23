"""
calc_prominence_kyrgyzstan.py — Compute topographic prominence for Kyrgyzstan peaks.

Uses Copernicus GLO-30 (~30m) DEM tiles from the public AWS S3 bucket and a
cell-sort union-find algorithm to find the key col for each peak.

Usage:
    pip install numpy requests rasterio
    python calc_prominence_kyrgyzstan.py [input.csv [output.csv]]

Tiles are downloaded automatically to dem_cache_kgz/ and cached.

Bbox: eastern Kyrgyzstan (lat 39-43, lon 74-81) = 28 tiles, ~363M cells.
Peak RAM ~9GB. Covers all Tian Shan including Khan Tengri and Pobeda.
Excludes western ranges (Fergana/Chatkal) and northern steppe.
"""

import csv
import sys
import time
from pathlib import Path

import numpy as np
import requests

try:
    import rasterio
except ImportError:
    sys.exit("rasterio required:  pip install rasterio")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR  = SCRIPT_DIR / "dem_cache_kgz"
INPUT_CSV  = SCRIPT_DIR / "kyrgyzstan_peaks.csv"
OUTPUT_CSV = SCRIPT_DIR / "kyrgyzstan_prom.csv"

# Bounding box: eastern Kyrgyzstan — Bishkek area east to Chinese border.
# Drops the western ranges (Fergana/Chatkal, lon 69-74) and northern steppe
# (lat 43-44). Keeps all Tian Shan including Khan Tengri and Pobeda.
# 28 tiles, ~363M cells, ~9GB peak RAM (vs 60 tiles / 18GB for full extent).
LAT_MIN, LAT_MAX = 39, 43   # exclusive upper bound  (4 rows)
LON_MIN, LON_MAX = 74, 81   # exclusive upper bound  (7 cols)

# Copernicus GLO-30 public tiles on AWS (no auth required).
COP_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
NODATA   = -32768


# ---------------------------------------------------------------------------
# Tile helpers
# ---------------------------------------------------------------------------

def cop_tile_key(lat: int, lon: int) -> str:
    """Copernicus tile stem (used as both directory name and .tif filename)."""
    ns = f"N{lat:02d}"      if lat >= 0 else f"S{abs(lat):02d}"
    ew = f"E{abs(lon):03d}" if lon >= 0 else f"W{abs(lon):03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def cop_tile_url(lat: int, lon: int) -> str:
    key = cop_tile_key(lat, lon)
    return f"{COP_BASE}/{key}/{key}.tif"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_tiles(cache_dir: Path) -> None:
    """Download individual Copernicus COG tiles for the bounding box."""
    cache_dir.mkdir(exist_ok=True)
    total = (LAT_MAX - LAT_MIN) * (LON_MAX - LON_MIN)
    done = 0
    for lat in range(LAT_MIN, LAT_MAX):
        for lon in range(LON_MIN, LON_MAX):
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
        data     = ds.read(1).astype(np.float32)
        nd_value = ds.nodata
    if nd_value is not None:
        data[data == nd_value] = NODATA
    data[data < -9000] = NODATA
    return data.astype(np.int16)


def load_dem(cache_dir: Path) -> tuple[np.ndarray, tuple[float, float, float]]:
    """
    Stitch Copernicus tiles into a single array.

    Returns:
        dem           int16 array, shape (nrows, ncols)
        geotransform  (north_lat, west_lon, cell_deg)
    """
    tile_h = tile_w = 0
    for lat in range(LAT_MIN, LAT_MAX):
        for lon in range(LON_MIN, LON_MAX):
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
    n_lat    = LAT_MAX - LAT_MIN
    n_lon    = LON_MAX - LON_MIN
    nrows    = n_lat * tile_h
    ncols    = n_lon * tile_w

    print(f"  Allocating DEM array: {nrows}×{ncols} = {nrows*ncols:,} cells "
          f"({nrows*ncols*2/1e9:.1f} GB int16)…")
    dem = np.full((nrows, ncols), NODATA, dtype=np.int16)

    for lat in range(LAT_MIN, LAT_MAX):
        for lon in range(LON_MIN, LON_MAX):
            tpath = cache_dir / f"{cop_tile_key(lat, lon)}.tif"
            if not tpath.exists():
                print(f"  WARNING: {tpath.name} not found — leaving NODATA")
                continue
            tile = load_tif(tpath)
            row0 = (LAT_MAX - 1 - lat) * tile_h
            col0 = (lon - LON_MIN) * tile_w
            dem[row0:row0 + tile_h, col0:col0 + tile_w] = tile

    gt = (float(LAT_MAX), float(LON_MIN), cell_deg)
    return dem, gt


def latlon_to_rc(lat: float, lon: float,
                 gt: tuple[float, float, float]) -> tuple[int, int]:
    north, west, cell = gt
    return round((north - lat) / cell), round((lon - west) / cell)


# ---------------------------------------------------------------------------
# Prominence — cell-sort union-find
# ---------------------------------------------------------------------------

def compute_prominence(
    dem: np.ndarray,
    peaks: list[tuple[int, int, int, float]],
) -> dict[int, int]:
    """
    Cell-sort prominence algorithm.

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
            parent[i] = parent.item(parent.item(i))
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
# Main
# ---------------------------------------------------------------------------

def load_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _in_bbox(row: dict) -> bool:
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
    except (ValueError, KeyError):
        return False
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def main() -> None:
    args = sys.argv[1:]
    input_path  = Path(args[0]) if args       else INPUT_CSV
    output_path = Path(args[1]) if len(args) > 1 else OUTPUT_CSV

    # 1. Load peaks and filter to bbox
    print(f"Loading peaks from {input_path}…")
    rows = load_rows(input_path)
    before = len(rows)
    rows = [r for r in rows if _in_bbox(r)]
    print(f"  {before} rows → {len(rows)} within bbox "
          f"(lat {LAT_MIN}–{LAT_MAX}, lon {LON_MIN}–{LON_MAX})")

    # 2. Download DEM tiles
    print(f"Downloading DEM tiles (lat {LAT_MIN}-{LAT_MAX}, lon {LON_MIN}-{LON_MAX})…")
    download_tiles(CACHE_DIR)

    # 3. Stitch DEM
    print("Loading DEM…")
    dem, gt = load_dem(CACHE_DIR)
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

    # 7. Write output
    fieldnames = list(rows[0].keys()) if rows else []
    if "prominence_calc" not in fieldnames:
        fieldnames.append("prominence_calc")

    kc_lookup = {peak_idx: key_col.get(peak_idx) for peak_idx, *_ in peaks}
    for peak_idx, _r, _c, elev in peaks:
        kc = kc_lookup[peak_idx]
        rows[peak_idx]["prominence_calc"] = (
            int(round(elev - kc)) if kc is not None else ""
        )

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWritten {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
