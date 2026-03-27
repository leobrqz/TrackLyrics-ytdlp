"""
core/playlist_manager.py
CRUD operations for playlists and playlist_tracks tables.
"""
from __future__ import annotations
from typing import Optional

from core.database import get_connection
from core.library import _row_to_track
from core.models import Playlist, Track


def _row_to_playlist(row) -> Playlist:
    return Playlist(id=row["id"], name=row["name"], created_at=row["created_at"])


# ---------------------------------------------------------------------------
# Playlist CRUD
# ---------------------------------------------------------------------------

def create_playlist(name: str) -> int:
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO playlists (name) VALUES (?)", (name,)
            )
            return cur.lastrowid
    finally:
        conn.close()


def rename_playlist(playlist_id: int, new_name: str) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE playlists SET name = ? WHERE id = ?", (new_name, playlist_id)
            )
    finally:
        conn.close()


def delete_playlist(playlist_id: int) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    finally:
        conn.close()


def get_all_playlists() -> list[Playlist]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM playlists ORDER BY created_at ASC"
        ).fetchall()
        return [_row_to_playlist(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Playlist ↔ Track relations
# ---------------------------------------------------------------------------

def get_playlist_tracks(playlist_id: int) -> list[Track]:
    """Return ordered tracks for a playlist."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT t.*
            FROM tracks t
            JOIN playlist_tracks pt ON pt.track_id = t.id
            WHERE pt.playlist_id = ?
            ORDER BY pt.sort_order ASC
            """,
            (playlist_id,),
        ).fetchall()
        return [_row_to_track(r) for r in rows]
    finally:
        conn.close()


def add_track_to_playlist(playlist_id: int, track_id: int) -> None:
    """Append a track to the end of a playlist."""
    conn = get_connection()
    try:
        with conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            next_order = row["next_order"]
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, sort_order) VALUES (?, ?, ?)",
                (playlist_id, track_id, next_order),
            )
    finally:
        conn.close()


def remove_track_from_playlist(playlist_id: int, track_id: int) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                (playlist_id, track_id),
            )
    finally:
        conn.close()


def reorder_playlist(playlist_id: int, ordered_track_ids: list[int]) -> None:
    """Reassign sort_order based on the given ordered list of track IDs."""
    conn = get_connection()
    try:
        with conn:
            for idx, track_id in enumerate(ordered_track_ids):
                conn.execute(
                    "UPDATE playlist_tracks SET sort_order = ? WHERE playlist_id = ? AND track_id = ?",
                    (idx, playlist_id, track_id),
                )
    finally:
        conn.close()


def is_track_in_playlist(playlist_id: int, track_id: int) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()
