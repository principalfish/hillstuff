# Hills & Runs

Local Flask webapp for planning and analyzing hillwalking and running routes.

## Setup

```
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy pydantic mypy
python app.py
```

Or simply: `./server.sh` (creates venv and installs dependencies automatically if needed).

Visit http://localhost:5000

## Features

### Big Runs
Plan long-distance routes with detailed leg-by-leg analysis:
- **Route management** — create, edit, and delete routes; each route has a name, optional location (lat/lon), and notes
- **Leg-by-leg breakdown** — add/edit legs with distance, ascent, and descent; first leg is the start point
- **Tiered pacing** — configure flat, ascent, and descent pace per tier; tiers switch with fatigue (ordered by cumulative time, last tier is unbounded). Ascent pace is per 125m, descent per 375m.
- **Start time** — set a start time to see clock times at each checkpoint
- **Solar data** — set a date to see sunrise/sunset times and where they fall on the route; auto-adjusts for BST
- **Manual time overrides** — override the calculated time for any leg; clear to revert to calculated
- **Attempt tracking** — log previous attempts with per-leg times; compare against current calculation with configurable diff thresholds
- **Notes** — freeform notes field per route
- **CSV import** — paste or upload CSV data; parsed client-side for review before saving
- **Location picker** — Leaflet/OpenStreetMap map for setting route lat/lon (no API key needed)

### Hills (Munros, Corbetts, Wainwrights)
Track completion logs for Scottish and English hill lists:
- **Three lists** — Munros (Scottish 3000ft+), Corbetts (Scottish 2500–3000ft), Wainwrights (Lake District fells)
- **Completion tracking** — log ascent dates per hill; multiple ascents supported
- **Progress summary** — count of climbed vs total, with per-year breakdown (new hills and total ascents each year, cumulative running total)
- **Hill data** — name, height, rank, and region per hill; pre-populated via import scripts
- **Add / edit / delete** — manage hills and ascent records

### Activity Log
Per-year log of walks, runs, and cycles:
- **Year view** — tabular log with sortable columns (date, km, ascent, type, region, Munros, Corbetts, Wainwrights, rating) and a text filter (region, with, hills, notes)
- **Summary** — hill type grid (run / walk / total per Munro / Corbett / Wainwright) and average rating
- **New entry** — form for current year with hill picker (auto-counts Munros / Corbetts / Wainwrights from linked hills and updates hills_text)
- **Edit entry** — edit any existing entry; hill changes sync HillAscent records automatically
- **CSV import** — paste CSV with flexible column order; column reference shown on page; year selector
- **Friendly dates** — stored as ISO (for sorting), displayed as "2nd January"
- Historical data 2019–2026 imported from spreadsheet exports via `old_data/import_all.py` and `old_data/import_2025.py`

## Tech stack
- Flask + Jinja2 (server-rendered, no build step)
- SQLite via SQLAlchemy ORM (Flask-SQLAlchemy)
- Pydantic for input validation, mypy for type checking
- Leaflet / OpenStreetMap for the location picker
- Vanilla JS only, no JS framework

## Database
`walks.db` is created automatically on first run. It is backed up to `walks.db.bak` on every startup.

`walks_template.db` is a reference database (Finlay Wild splits + personal attempt splits for key routes) used as a starting point on new installs.
