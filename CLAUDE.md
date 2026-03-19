# Project: Hills & Runs

## Architecture
- Flask app factory pattern in `app.py`, features as Blueprints
- SQLite database (`walks.db`) via SQLAlchemy ORM (Flask-SQLAlchemy)
- Models, DB, and solar calculator live in `walks/` package
- Pydantic for form validation (`walks/schemas.py`), mypy for type checking
- Server-rendered with Jinja2 templates, minimal vanilla JS
- No build step, no JS framework

## Structure
```
app.py              — App factory, registers blueprints, home route, friendly_date filter
schema.sql          — Reference SQL (not executed; models are source of truth)
walks/              — Walks (Big Runs) blueprint + shared modules
  __init__.py       — Blueprint registration
  db.py             — Flask-SQLAlchemy init, create_all
  models.py         — SQLAlchemy model definitions
  routes.py         — All route handlers
  schemas.py        — Pydantic validation models for form input
  calc.py           — Pace tier calculation, time formatting
  solar.py          — Sunrise/sunset calculator (no external deps)
  templates/walks/  — detail.html, list.html, form.html
  static/walks/     — detail.js
hills/              — Hills blueprint (Munros, Corbetts, Wainwrights)
  models.py         — Hill, HillAscent
  routes.py         — List, new/edit/delete hill, add/delete ascent
  templates/hills/
logs/               — Activity Log blueprint
  models.py         — LogEntry, LogEntryHill
  routes.py         — Year view, new/edit entry, CSV import, hills API
  templates/logs/   — year.html, new_entry.html, edit_entry.html, import.html
  static/logs/      — log.js (hill picker, table sort/filter)
templates/          — Shared templates (base.html, home.html)
static/             — Shared CSS, favicon
old_data/           — Import scripts and source CSVs
  import_all.py     — Imports activity logs 2019–2024, 2026
  import_2025.py    — Imports 2025 activity log
  import_munros.py, import_corbetts.py, import_wainwrights.py
  import_tranters.py, import_shiel.py, import_mamores.py, etc.
walks_template.db   — Reference DB with Finlay Wild splits + personal attempt splits
```

## Typing
- All Python code must have type annotations (function signatures, return types)
- mypy runs as a pre-commit hook — code must pass `mypy walks/ app.py --config-file=mypy.ini`
- `disallow_untyped_defs` and `disallow_incomplete_defs` are enforced in `mypy.ini`
- Use `model_validate()` (not direct constructor) when passing form strings to Pydantic models with numeric fields

## Testing
- Run tests: `./test.sh` (or `pytest tests/` from venv)
- Tests use in-memory SQLite — no file DB created
- 89 tests across 4 files: calc, solar, schemas, routes
- Route tests use the `sample_route` fixture for a 3-leg test route

## Key patterns

### Walks (Big Runs)
- Legs use a single `location` column (not start/end). First leg = start point with 0 distance/ascent/descent.
- Pace tiers are ordered by `up_to_minutes` ascending, NULL = unbounded final tier. Tier at leg start determines pace for that leg. Ascent pace is per 125m, descent pace is per 375m.
- Time overrides stored separately from legs. Clearing an override deletes the row.
- Solar times auto-adjust for BST (last Sunday March to last Sunday October).
- Leaflet map (OpenStreetMap tiles) for lat/lon picker on route form — no API key needed.
- CSV import (walks) parses client-side into the manual table for review before saving.

### Hills
- `Hill` has `hill_type` values `munro`, `corbett`, `wainwright`; slugs map to these.
- `HillAscent` records are synced automatically when LogEntry hills are added/edited/removed.

### Activity Log
- `LogEntry` stores `date` as ISO (YYYY-MM-DD) for sorting; displayed via `friendly_date` Jinja filter registered in `app.py`.
- `friendly_date` converts `"2025-01-02"` → `"2nd January"` using `_ordinal(n)` helper.
- `LogEntryHill` links log entries to specific hills; hill counts (munros/corbetts/wainwrights) are stored on the entry for fast aggregation.
- Hill counts in the year summary (run/walk/total) are computed live from `LogEntry` records — no cached meta table.
- `_sync_hill_ascents(entry, hill_ids, old_date=None)`: removes old `HillAscent` rows (on `old_date` or `entry.date`), adds new ones. Call before updating `entry.date`.
- CSV import (logs) is server-side; columns may be in any order; header row required.
- `CURRENT_YEAR = datetime.date.today().year` — new entry and import only allowed for current year by default.
- Region carryforward with `^` used in spreadsheet source data (handled in import scripts only).

## Running
```
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy pydantic mypy
python app.py
```

## Database
- `walks.db` is auto-created on first run via `db.create_all()`
- Auto-backed up to `walks.db.bak` on every app startup
- **Never delete `walks.db` without backing it up first.** Copy to `walks.db.bak`, apply the migration, then reimport data. If the migration is too breaking for data to survive, ask the user before proceeding.
- For verification/testing, use `SQLALCHEMY_DATABASE_URI=sqlite:///walks_test.db` — never test against `walks.db`
- `walks_template.db` — reference DB used as a starting point on new installs; contains Finlay Wild splits for all routes and personal dated attempts for Tranter's 2024, Shiel 2024, Mamores 2025.
