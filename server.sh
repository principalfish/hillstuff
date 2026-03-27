#!/bin/bash
source ~/.bashrc
DIR="$(dirname "$0")"

if [ ! -d "$DIR/venv" ]; then
    echo "Creating venv..."
    python3 -m venv "$DIR/venv"
    source "$DIR/venv/bin/activate"
    pip install flask flask-sqlalchemy pydantic mypy pre-commit pytest
else
    source "$DIR/venv/bin/activate"
fi

if [ -n "$WALKS_DB_SYNC" ] && [ -f "$WALKS_DB_SYNC" ]; then
    echo "Copying DB from sync path: $WALKS_DB_SYNC"
    cp "$WALKS_DB_SYNC" walks.db
fi

python app.py
