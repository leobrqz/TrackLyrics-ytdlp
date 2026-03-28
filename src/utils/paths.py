"""
utils/paths.py
Single source of truth for all filesystem paths used by the application.
All directories are created on import if they do not already exist.
"""
from pathlib import Path

# Project root is the parent of the src/ directory
APP_ROOT: Path = Path(__file__).resolve().parent.parent.parent

DB_PATH: Path = APP_ROOT / "library.db"
SETTINGS_JSON_PATH: Path = APP_ROOT / "app_settings.json"
TRACKS_DIR: Path = APP_ROOT / "tracks"
TEMP_DIR: Path = APP_ROOT / "temp"
LOGS_DIR: Path = APP_ROOT / "logs"

# Create directories on import (safe, idempotent)
for _dir in (TRACKS_DIR, TEMP_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
