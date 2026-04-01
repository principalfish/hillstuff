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

# On startup, restore the DB from WALKS_DB_SYNC (a Google Drive path) if set.
# On Mac, Google Drive files are accessible directly, so we can cp normally.
# On WSL, Google Drive uses a Windows virtual filesystem that WSL can't access,
# so we convert both paths to Windows paths and use PowerShell to do the copy.
if [ -n "$WALKS_DB_SYNC" ]; then
    if [[ "$(uname)" == "Darwin" ]]; then
        if [ -f "$WALKS_DB_SYNC" ]; then
            echo "Copying DB from sync path: $WALKS_DB_SYNC"
            cp "$WALKS_DB_SYNC" walks.db
        else
            echo "Sync path not found, skipping restore: $WALKS_DB_SYNC"
        fi
    else
        SYNC_WIN=$(wslpath -w "$WALKS_DB_SYNC" 2>/dev/null)
        DEST_WIN=$(wslpath -w "$(pwd)/walks.db" 2>/dev/null)
        if [ -n "$SYNC_WIN" ] && [ -n "$DEST_WIN" ]; then
            echo "Copying DB from sync path: $WALKS_DB_SYNC"
            powershell.exe -Command "if (Test-Path '$SYNC_WIN') { Copy-Item -Path '$SYNC_WIN' -Destination '$DEST_WIN' -Force; Write-Host 'done' } else { Write-Host 'not found' }"
        fi
    fi
fi

python app.py
