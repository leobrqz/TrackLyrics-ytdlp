"""
utils/paths.py
Single source of truth for all filesystem paths used by the application.
All directories are created on import if they do not already exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DEV_ROOT: Path = Path(__file__).resolve().parent.parent.parent

_FROZEN_DATA_DIRNAME = "tracklyrics"
_PORTABLE_APP_ROOT_NAME = "TrackLyrics"

# CSIDL_PERSONAL — Windows Shell "Documents" / "My Documents" (correct path per locale)
_CSIDL_PERSONAL = 5


def _windows_shell_documents() -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(260)
        # SHGetFolderPathW(hwnd, csidl, hToken, dwFlags, pszPath)
        hr = ctypes.windll.shell32.SHGetFolderPathW(
            None, _CSIDL_PERSONAL, None, 0, buf
        )
        if hr != 0:
            return None
        path = Path(buf.value)
        return path if path.is_dir() else None
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _frozen_exe_parent() -> Path:
    return Path(sys.executable).resolve().parent


def _frozen_app_data_root() -> Path:
    if sys.platform == "win32":
        shell_docs = _windows_shell_documents()
        if shell_docs is not None:
            return shell_docs / _FROZEN_DATA_DIRNAME
    return _frozen_exe_parent() / _PORTABLE_APP_ROOT_NAME


if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _BUNDLE_ROOT: Path = Path(sys._MEIPASS)
    APP_ROOT: Path = _frozen_app_data_root()
else:
    _BUNDLE_ROOT = _DEV_ROOT
    APP_ROOT = _DEV_ROOT

ICON_PATH: Path = _BUNDLE_ROOT / "assets" / "icon.ico"

DB_PATH: Path = APP_ROOT / "library.db"
SETTINGS_JSON_PATH: Path = APP_ROOT / "app_settings.json"
TRACKS_DIR: Path = APP_ROOT / "tracks"
TEMP_DIR: Path = APP_ROOT / "temp"
LOGS_DIR: Path = APP_ROOT / "logs"

# Create directories on import (safe, idempotent)
for _dir in (TRACKS_DIR, TEMP_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
