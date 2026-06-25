# Peak data scripts

Tools for building peak datasets: fetch peaks from OpenStreetMap, compute their
topographic prominence from elevation tiles, and filter to a bounding box. Output
CSVs feed the `peaks_map.html` viewer (served by `../serve.py`).

## Layout

```
misc-scripts/
├── serve.py            Dev server for peaks_map.html (lists csv/ and gpx/)
├── peaks_map.html      Leaflet map viewer
├── csv/                Peak data CSVs (inputs and outputs of these scripts)
├── gpx/                GPX tracks (overlaid on the map)
└── scripts/
    ├── fetch_peaks.py        Fetch peaks from OpenStreetMap (Overpass API)
    ├── calc_prominence.py    Compute prominence from Copernicus DEM tiles
    └── filter_bbox.py        Filter a peaks CSV to a lat/lon box
```

## Pipeline

```
fetch_peaks.py  ──►  csv/<region>_peaks.csv  ──►  calc_prominence.py  ──►  csv/<region>_prom.csv
                                                          │
                                          filter_bbox.py (optional, any stage)
```

Run all commands from the `misc-scripts/` directory.

```sh
pip install requests numpy rasterio   # rasterio/numpy only needed for calc_prominence.py
```

---

## `fetch_peaks.py`

Fetch `natural=peak` nodes (with an `ele` tag) from OpenStreetMap via the
Overpass API, for a bounding box. Drops peaks whose OSM `prominence` tag is set
and below `--min-prominence`; untagged peaks are kept (their prominence is
computed later by `calc_prominence.py`).

```
python scripts/fetch_peaks.py --bbox S,W,N,E [options]
```

| Option | Default | Meaning |
|---|---|---|
| `--bbox S,W,N,E` | *(required)* | Bounding box, float degrees: south,west,north,east |
| `--min-prominence M` | `200` | Drop peaks with an OSM prominence tag below `M` |
| `--min-elevation M` | `500` | Server-side elevation floor passed to Overpass |
| `--name-langs LANGS` | `en` | Comma-separated name fallback order, e.g. `en,ru,ky` |
| `--output FILE` | `csv/peaks_<bbox>.csv` | Output CSV path |

The `name` column is filled by trying each `--name-langs` code in order
(`name:en`, `name:ru`, …), falling back to the generic `name` tag. A `name_<lang>`
column is also emitted per requested language. Output is sorted by elevation.

**Examples**

```sh
# Pyrenees
python scripts/fetch_peaks.py --bbox 42.0,-2.0,43.5,3.5 \
    --output csv/pyrenees_peaks.csv

# Eastern Kyrgyzstan (Tian Shan)
python scripts/fetch_peaks.py --bbox 39.0,74.0,43.0,81.0 \
    --name-langs en,ru,ky --output csv/kyrgyzstan_peaks.csv

# Western Kyrgyzstan (Fergana/Chatkal/Talas)
python scripts/fetch_peaks.py --bbox 39.0,69.0,43.0,74.0 \
    --name-langs en,ru,ky --output csv/kyrgyzstan_peaks_west.csv
```

---

## `calc_prominence.py`

Compute topographic prominence for each peak in a CSV. Downloads Copernicus
GLO-30 (~30 m) DEM tiles from the public AWS bucket (one per integer lat/lon
degree), stitches them, and runs a cell-sort union-find to find each peak's key
col. Adds a `prominence_calc` column.

```
python scripts/calc_prominence.py --input csv/<region>_peaks.csv [options]
```

| Option | Default | Meaning |
|---|---|---|
| `--input FILE` | `csv/peaks.csv` | Input peaks CSV |
| `--bbox LAT_MIN,LON_MIN,LAT_MAX,LON_MAX` | *(derived from CSV)* | **Integer** tile bounds; override the auto-derived extent |
| `--pad DEG` | `0` | Degrees added around the derived extent (ignored when `--bbox` is set) |
| `--output FILE` | `<input>_prom.csv` | Output CSV path |
| `--cache-dir DIR` | `dem_cache_<bbox>/` | DEM tile cache (auto-named, gitignored) |
| `--min-prominence M` | `0` (no trim) | If > 0, drop peaks with computed prominence below `M` |

**Bbox is optional.** By default it's derived from the input CSV: the min/max
lat/lon of the peaks, floored/ceiled to whole integer tiles (one tile is
downloaded per degree), plus `--pad` degrees. This reproduces the hand-tuned
boxes used previously — e.g. `csv/kyrgyzstan_peaks_west.csv` derives `39,69,43,74`.

Pass `--bbox` explicitly to **constrain** the extent — e.g. if a CSV spans more
ground than you want to process, to keep download size and RAM down.

A peak's key col can lie just outside a tight extent, in which case it's reported
as having no prominence (unbounded). Raise `--pad` to extend the box if peaks
near the edge come back blank.

With `--min-prominence M`, peaks whose `prominence_calc` is calculably below `M`
are dropped; peaks with no key col found inside the box (effectively unbounded,
e.g. a range high point) and unmapped peaks are kept.

> **Cost:** large boxes download GBs of tiles and use several GB of RAM
> (~9 GB / ~363M cells for the 28-tile eastern-Kyrgyzstan box). Tiles are cached
> between runs.

**Examples**

```sh
# Pyrenees — bbox auto-derived from the peaks
python scripts/calc_prominence.py \
    --input csv/pyrenees_peaks.csv --output csv/pyrenees_prom.csv

# Eastern Kyrgyzstan — explicit bbox to constrain extent, trim to >= 200 m
python scripts/calc_prominence.py --bbox 39,74,43,81 \
    --input csv/kyrgyzstan_peaks.csv --output csv/kyrgyzstan_prom.csv \
    --min-prominence 200

# Western Kyrgyzstan — auto bbox with a little padding
python scripts/calc_prominence.py --pad 0.5 \
    --input csv/kyrgyzstan_peaks_west.csv --output csv/kyrgyzstan_prom_west.csv \
    --min-prominence 200
```

---

## `filter_bbox.py`

Filter a peaks CSV to a lat/lon box. Useful for cropping a large dataset to a
map view without re-fetching.

```
python scripts/filter_bbox.py <lat_min> <lat_max> <lon_min> <lon_max> [input.csv [output.csv]]
```

- Input defaults to `csv/merged_pyrenees_prom_195.csv`.
- Output defaults to the input filename with a `_bbox` suffix.

**Example**

```sh
python scripts/filter_bbox.py 42.3 43.2 -1.0 2.8 \
    csv/peaks_filtered_195m.csv csv/peaks_view.csv
```
