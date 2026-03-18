-- REFERENCE ONLY — this file is no longer executed.
-- The source of truth is models.py (SQLAlchemy models).
--
-- Big Runs: route planning with pace tiers and attempt tracking
CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL DEFAULT 56.8,
    longitude REAL DEFAULT -5.1,
    start_time TEXT DEFAULT '06:00',  -- HH:MM format
    start_date TEXT DEFAULT '2026-06-01',  -- YYYY-MM-DD format
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL,
    leg_num INTEGER NOT NULL,
    location TEXT NOT NULL,
    distance_km REAL NOT NULL DEFAULT 0,
    ascent_m REAL NOT NULL DEFAULT 0,
    descent_m REAL NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pace_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL,
    up_to_minutes REAL,  -- NULL = unbounded final tier
    flat_pace_min_per_km REAL NOT NULL,
    ascent_pace_min_per_125m REAL NOT NULL DEFAULT 0,
    descent_pace_min_per_375m REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS time_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL,
    leg_id INTEGER NOT NULL UNIQUE,
    override_minutes REAL NOT NULL,
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE,
    FOREIGN KEY (leg_id) REFERENCES legs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    date TEXT,
    notes TEXT,
    FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attempt_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    leg_id INTEGER NOT NULL,
    actual_time_minutes REAL,
    FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (leg_id) REFERENCES legs(id) ON DELETE CASCADE
);
