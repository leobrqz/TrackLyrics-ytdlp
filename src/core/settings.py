"""
core/settings.py
Key-value settings store backed by a separate app_settings.db SQLite file.
Used for persisting UI preferences like the active theme.
"""
import sqlite3
from typing import Optional

from utils.paths import SETTINGS_DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SETTINGS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = _get_conn()
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = _get_conn()
    try:
        _ensure_table(conn)
        with conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
    finally:
        conn.close()
