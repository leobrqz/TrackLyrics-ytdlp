"""
core/models.py
Pure dataclass DTOs shared across the entire application.
No database logic lives here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MediaFile:
    id: int
    track_id: int
    file_name: str
    format_type: str       # 'mp3' | 'wav' (legacy rows may list other formats)
    has_audio: bool


@dataclass
class LyricsRow:
    track_id: int
    original_path: Optional[str]
    ptbr_path: Optional[str]
    original_url: Optional[str]
    ptbr_url: Optional[str]
    has_original: bool
    has_ptbr: bool


@dataclass
class Track:
    id: int
    title: str
    artist: str
    duration: int              # seconds
    favorite: bool
    folder_name: str           # e.g. "Audioslave - Like a Stone - 1"
    source_url: str
    created_at: str
    # Populated lazily by library helpers — not stored in DB columns
    media_files: list[MediaFile] = field(default_factory=list)
    lyrics: Optional[LyricsRow] = None


@dataclass
class Playlist:
    id: int
    name: str
    created_at: str


@dataclass
class PlaylistTrack:
    id: int
    playlist_id: int
    track_id: int
    sort_order: int
