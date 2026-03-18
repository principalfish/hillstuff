# Hills & Runs

Local Flask webapp for planning and analyzing hillwalking and running routes.

## Features

### Big Runs
Plan long-distance routes with detailed leg-by-leg analysis:
- **Route management** — create routes manually or import from CSV
- **Tiered pacing** — configure flat, ascent, and descent pace that changes with fatigue (e.g. faster early, slower later)
- **Time of day** — set a start time to see clock times at each checkpoint
- **Solar data** — set a date and location to see sunrise/sunset times and where they fall on the route
- **Manual overrides** — override calculated time for any leg
- **Attempt tracking** — log previous attempts and compare times with configurable diffs

### Planned
- Munro / Corbett / Wainwright completion logs
- Per-year walk/run activity log

## Setup

```
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy pydantic mypy
python app.py
```

Or simply: `./server.sh` (creates venv automatically if needed).

Visit http://localhost:5000

## CSV format

```
leg_num,location,distance_km,ascent_m,descent_m
1,Start Point,0,0,0
2,Checkpoint 1,8.0,346,82
3,Checkpoint 2,3.5,383,299
```

Descent column is optional (defaults to 0). First leg should be the start location with zeroes.

## Tech stack
- Flask + Jinja2 (server-rendered)
- SQLite via SQLAlchemy ORM (Flask-SQLAlchemy)
- Pydantic for input validation, mypy for type checking
- Leaflet/OpenStreetMap for location picker
- No build step, no JS framework
