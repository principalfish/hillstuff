import os
import platform
import shutil
import subprocess

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

PROJECT_ROOT: str = os.path.dirname(os.path.dirname(__file__))
DATABASE: str = os.path.join(PROJECT_ROOT, 'walks.db')
SYNC_PATH: str | None = os.environ.get('WALKS_DB_SYNC', '').strip() or None


def sync_db() -> None:
    """Copy local DB to SYNC_PATH. Works on macOS (direct copy) and WSL (via PowerShell)."""
    if not SYNC_PATH:
        return
    try:
        if platform.system() == 'Darwin':
            shutil.copy2(DATABASE, SYNC_PATH)
            print(f"[sync] {DATABASE} -> {SYNC_PATH}")
        else:
            src = subprocess.run(["wslpath", "-w", DATABASE], capture_output=True, text=True, timeout=5)
            dst = subprocess.run(["wslpath", "-w", SYNC_PATH], capture_output=True, text=True, timeout=5)
            if src.returncode != 0 or dst.returncode != 0:
                print(f"[sync] wslpath failed: src={src.stderr} dst={dst.stderr}")
                return
            src_w, dst_w = src.stdout.strip(), dst.stdout.strip()
            r = subprocess.run(
                ["powershell.exe", "-Command",
                 f"Copy-Item -Path '{src_w}' -Destination '{dst_w}' -Force"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                print(f"[sync] {src_w} -> {dst_w}")
            else:
                print(f"[sync] failed: {r.stderr.strip()}")
    except Exception as e:
        print(f"[sync] error: {e}")


def init_app(app: Flask) -> None:
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', f'sqlite:///{DATABASE}')
    db.init_app(app)


def init_db() -> None:
    db.create_all()
