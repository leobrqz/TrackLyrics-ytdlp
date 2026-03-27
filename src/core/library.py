"""
core/library.py
CRUD operations for tracks, media_files, and lyrics tables.
All functions open their own connection and close it when done.
"""
from __future__ import annotations
from typing import Optional

from core.database import get_connection
from core.models import LyricsRow, MediaFile, Track


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_track(row) -> Track:
    return Track(
        id=row["id"],
        title=row["title"],
        artist=row["artist"],
        duration=row["duration"],
        favorite=bool(row["favorite"]),
        folder_name=row["folder_name"],
        source_url=row["source_url"],
        created_at=row["created_at"],
    )


def _row_to_media_file(row) -> MediaFile:
    return MediaFile(
        id=row["id"],
        track_id=row["track_id"],
        file_name=row["file_name"],
        format_type=row["format_type"],
        has_audio=bool(row["has_audio"]),
        has_video=bool(row["has_video"]),
    )


def _row_to_lyrics(row) -> LyricsRow:
    return LyricsRow(
        track_id=row["track_id"],
        original_path=row["original_path"],
        ptbr_path=row["ptbr_path"],
        original_url=row["original_url"],
        ptbr_url=row["ptbr_url"],
        has_original=bool(row["has_original"]),
        has_ptbr=bool(row["has_ptbr"]),
    )


# ---------------------------------------------------------------------------
# Track CRUD
# ---------------------------------------------------------------------------

def insert_track(
    title: str,
    artist: str,
    duration: int,
    folder_name: str,
    source_url: str,
    media_files: list[dict],   # list of {file_name, format_type, has_audio, has_video}
) -> int:
    """
    Insert a track + its media files + an empty lyrics row in one transaction.
    Returns the new track_id.
    """
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO tracks (title, artist, duration, folder_name, source_url)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, artist, duration, folder_name, source_url),
            )
            track_id = cur.lastrowid

            for mf in media_files:
                conn.execute(
                    """
                    INSERT INTO media_files (track_id, file_name, format_type, has_audio, has_video)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (track_id, mf["file_name"], mf["format_type"], mf["has_audio"], mf["has_video"]),
                )

            # Create a blank lyrics row — will be updated after scraping
            conn.execute(
                "INSERT INTO lyrics (track_id) VALUES (?)",
                (track_id,),
            )

        return track_id
    finally:
        conn.close()


def get_all_tracks() -> list[Track]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tracks ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_track(r) for r in rows]
    finally:
        conn.close()


def get_track_by_id(track_id: int) -> Optional[Track]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM tracks WHERE id = ?", (track_id,)
        ).fetchone()
        return _row_to_track(row) if row else None
    finally:
        conn.close()


def get_media_files(track_id: int) -> list[MediaFile]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM media_files WHERE track_id = ?", (track_id,)
        ).fetchall()
        return [_row_to_media_file(r) for r in rows]
    finally:
        conn.close()


def get_lyrics(track_id: int) -> Optional[LyricsRow]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM lyrics WHERE track_id = ?", (track_id,)
        ).fetchone()
        return _row_to_lyrics(row) if row else None
    finally:
        conn.close()


def update_favorite(track_id: int, value: bool) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE tracks SET favorite = ? WHERE id = ?",
                (int(value), track_id),
            )
    finally:
        conn.close()


def update_lyrics(
    track_id: int,
    original_path: Optional[str],
    ptbr_path: Optional[str],
    original_url: Optional[str],
    ptbr_url: Optional[str],
    has_original: bool,
    has_ptbr: bool,
) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                UPDATE lyrics
                SET original_path = ?, ptbr_path = ?, original_url = ?,
                    ptbr_url = ?, has_original = ?, has_ptbr = ?
                WHERE track_id = ?
                """,
                (original_path, ptbr_path, original_url, ptbr_url,
                 int(has_original), int(has_ptbr), track_id),
            )
    finally:
        conn.close()


def add_media_file(
    track_id: int,
    file_name: str,
    format_type: str,
    has_audio: bool,
    has_video: bool,
) -> None:
    """Add a converted format file for an existing track."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO media_files (track_id, file_name, format_type, has_audio, has_video)
                VALUES (?, ?, ?, ?, ?)
                """,
                (track_id, file_name, format_type, int(has_audio), int(has_video)),
            )
    finally:
        conn.close()


def delete_track(track_id: int) -> None:
    """Delete a track and all related rows via CASCADE."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
    finally:
        conn.close()


def track_exists(artist: str, title: str) -> bool:
    """Check for duplicate (artist, title) — case-insensitive."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM tracks WHERE LOWER(artist) = LOWER(?) AND LOWER(title) = LOWER(?)",
            (artist, title),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_all_tracks_full() -> list[Track]:
    """Return all tracks with media_files and lyrics populated."""
    tracks = get_all_tracks()
    for track in tracks:
        track.media_files = get_media_files(track.id)
        track.lyrics = get_lyrics(track.id)
    return tracks
