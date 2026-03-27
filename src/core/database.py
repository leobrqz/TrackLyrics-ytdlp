"""
core/database.py
SQLite connection management and schema initialisation.
Called once at application startup via init_db().
"""
import sqlite3
from pathlib import Path

from utils.paths import DB_PATH


def get_connection() -> sqlite3.Connection:
    """
    Open and return a SQLite connection with:
    - Row factory set to sqlite3.Row (dict-like access)
    - Foreign key enforcement enabled
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """
    Create all tables if they do not already exist.
    Safe to call on every application launch.
    """
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                artist      TEXT    NOT NULL DEFAULT '',
                duration    INTEGER NOT NULL DEFAULT 0,
                favorite    BOOLEAN NOT NULL DEFAULT 0,
                folder_name TEXT    NOT NULL,
                source_url  TEXT    NOT NULL DEFAULT '',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS media_files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id    INTEGER NOT NULL,
                file_name   TEXT    NOT NULL,
                format_type TEXT    NOT NULL,
                has_audio   BOOLEAN NOT NULL DEFAULT 0,
                has_video   BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lyrics (
                track_id        INTEGER PRIMARY KEY,
                original_path   TEXT,
                ptbr_path       TEXT,
                original_url    TEXT,
                ptbr_url        TEXT,
                has_original    BOOLEAN NOT NULL DEFAULT 0,
                has_ptbr        BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                track_id    INTEGER NOT NULL,
                sort_order  INTEGER NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (track_id)    REFERENCES tracks(id)    ON DELETE CASCADE
            );
        """)
    conn.close()
