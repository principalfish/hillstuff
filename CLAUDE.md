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
app.py              — App factory, registers blueprints, home route
schema.sql          — Reference SQL (not executed; models are source of truth)
walks/              — Walks blueprint + shared modules
  __init__.py       — Blueprint registration
  db.py             — Flask-SQLAlchemy init, create_all
  models.py         — SQLAlchemy model definitions
  routes.py         — All route handlers
  schemas.py        — Pydantic validation models for form input
  calc.py           — Pace tier calculation, time formatting
  solar.py          — Sunrise/sunset calculator (no external deps)
  templates/walks/  — detail.html, list.html, form.html
  static/walks/     — detail.js
templates/          — Shared templates (base.html, home.html)
static/             — Shared CSS, favicon
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
- Legs use a single `location` column (not start/end). First leg = start point with 0 distance/ascent/descent.
- Pace tiers are ordered by `up_to_minutes` ascending, NULL = unbounded final tier. Tier at leg start determines pace for that leg. Ascent pace is per 125m, descent pace is per 375m.
- Time overrides stored separately from legs. Clearing an override deletes the row.
- Solar times auto-adjust for BST (last Sunday March to last Sunday October).
- Leaflet map (OpenStreetMap tiles) for lat/lon picker on route form — no API key needed.
- CSV import parses client-side into the manual table for review before saving.

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

## Hills blueprint (`hills/`)
Tracks completion logs for Munros, Corbetts, and Wainwrights.
- Models: `Hill` (name, height_m, rank, region, hill_type) and `HillAscent` (hill_id, date) in `hills/models.py`
- Routes in `hills/routes.py`: list (`/<slug>`), new/edit/delete hill, add/delete ascent
- Slugs: `munros`, `corbetts`, `wainwrights` → mapped to `hill_type` values `munro`, `corbett`, `wainwright`
- Hill data pre-populated via import scripts in `old_data/`

## Future sections
- Per-year activity log (date, name, location, type, distance, ascent, time)
