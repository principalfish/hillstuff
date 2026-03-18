#!/bin/bash
DIR="$(dirname "$0")"

if [ ! -d "$DIR/venv" ]; then
    echo "Creating venv..."
    python3 -m venv "$DIR/venv"
    source "$DIR/venv/bin/activate"
    pip install flask flask-sqlalchemy pydantic mypy
else
    source "$DIR/venv/bin/activate"
fi

python app.py
