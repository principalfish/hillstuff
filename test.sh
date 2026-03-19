#!/bin/bash
DIR="$(dirname "$0")"
source "$DIR/venv/bin/activate"
python -m pytest tests/ "$@"
