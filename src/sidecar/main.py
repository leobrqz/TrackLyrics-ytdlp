"""JSONL command server for the Tauri desktop frontend."""
from __future__ import annotations

import json
import shutil
import sys
import threading
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

# The frozen sidecar and source-mode development entrypoint share this module.
SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import core.library as library
import core.playlist_manager as playlists
from core.database import init_db
from core.models import LyricsRow, MediaFile, Playlist, Track
from core.settings import (
    get_download_parallel_workers,
    get_download_queue_mode,
    get_lyrics_parallel_with_download,
    get_value,
    set_value,
)
from sidecar.worker import SidecarDownloadWorker
from utils.paths import TRACKS_DIR


class SidecarError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _int_id(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise SidecarError("INVALID_ARGUMENT", f"{name} must be a positive integer.")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise SidecarError("INVALID_ARGUMENT", f"{name} must be a positive integer.")
    if result < 1:
        raise SidecarError("INVALID_ARGUMENT", f"{name} must be a positive integer.")
    return result


def _contained_path(base: Path, relative: str) -> Optional[Path]:
    if not isinstance(relative, str) or not relative.strip():
        return None
    candidate_part = Path(relative)
    if candidate_part.is_absolute():
        return None
    base_real = base.resolve()
    candidate = (base_real / candidate_part).resolve()
    try:
        candidate.relative_to(base_real)
    except ValueError:
        return None
    return candidate


def _read_track_text(track: Track, relative: Optional[str]) -> Optional[str]:
    if not relative:
        return None
    folder = _contained_path(TRACKS_DIR, track.folder_name)
    if folder is None:
        return None
    file_path = _contained_path(folder, relative)
    if file_path is None or not file_path.is_file():
        return None
    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _media_dto(media: MediaFile) -> dict[str, Any]:
    return {
        "id": media.id,
        "trackId": media.track_id,
        "fileName": media.file_name,
        "formatType": media.format_type,
        "hasAudio": media.has_audio,
    }


def _lyrics_dto(track: Track, lyrics: Optional[LyricsRow], include_text: bool) -> Optional[dict[str, Any]]:
    if lyrics is None:
        return None
    result: dict[str, Any] = {
        "trackId": lyrics.track_id,
        "originalPath": lyrics.original_path,
        "ptbrPath": lyrics.ptbr_path,
        "originalUrl": lyrics.original_url,
        "ptbrUrl": lyrics.ptbr_url,
        "hasOriginal": lyrics.has_original,
        "hasPtbr": lyrics.has_ptbr,
        "searchStatus": lyrics.search_status,
    }
    if include_text:
        result["originalText"] = _read_track_text(track, lyrics.original_path)
        result["ptbrText"] = _read_track_text(track, lyrics.ptbr_path)
    return result


def _track_dto(track: Track, include_text: bool = False) -> dict[str, Any]:
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "duration": track.duration,
        "favorite": track.favorite,
        "folderName": track.folder_name,
        "sourceUrl": track.source_url,
        "createdAt": track.created_at,
        "mediaFiles": [_media_dto(media) for media in track.media_files],
        "lyrics": _lyrics_dto(track, track.lyrics, include_text),
    }


def _playlist_dto(playlist: Playlist, track_count: int = 0) -> dict[str, Any]:
    return {
        "id": playlist.id,
        "name": playlist.name,
        "createdAt": playlist.created_at,
        "trackCount": track_count,
    }


def _settings_dto() -> dict[str, Any]:
    try:
        volume = int(float(get_value("volume", 80)))
    except (TypeError, ValueError):
        volume = 80
    theme = str(get_value("theme", "dark") or "dark").lower()
    if theme not in {"dark", "light"}:
        theme = "dark"
    return {
        "theme": theme,
        "volume": max(0, min(100, volume)),
        "downloadQueueMode": get_download_queue_mode(),
        "downloadParallelWorkers": get_download_parallel_workers(),
        "lyricsParallelWithDownload": get_lyrics_parallel_with_download(),
    }


class SidecarServer:
    def __init__(self) -> None:
        self._stdout_lock = threading.Lock()
        self._stopping = threading.Event()
        self._downloads = SidecarDownloadWorker(self._emit_event)

    def _write(self, message: dict[str, Any]) -> None:
        encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self._stdout_lock:
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()

    def _emit_event(self, name: str, data: dict[str, Any]) -> None:
        self._write({"event": name, "data": data})

    def _response(self, request_id: Any, ok: bool, data: Any = None, error: Optional[dict[str, str]] = None) -> None:
        response: dict[str, Any] = {"id": request_id, "ok": ok}
        if ok:
            response["data"] = data
        else:
            response["error"] = error or {"code": "INTERNAL_ERROR", "message": "The request failed."}
        self._write(response)

    def serve(self) -> None:
        for raw_line in sys.stdin:
            if self._stopping.is_set():
                break
            line = raw_line.strip()
            if not line:
                continue
            request_id: Any = None
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise SidecarError("INVALID_REQUEST", "Each request must be a JSON object.")
                request_id = request.get("id")
                command = request.get("command")
                payload = request.get("payload", {})
                if not isinstance(command, str) or not command:
                    raise SidecarError("INVALID_REQUEST", "A command name is required.")
                if not isinstance(payload, dict):
                    raise SidecarError("INVALID_ARGUMENT", "The command payload must be an object.")
                result = self.dispatch(command, payload)
                self._response(request_id, True, result)
                if command == "app.shutdown":
                    self._stopping.set()
                    break
            except SidecarError as exc:
                self._response(request_id, False, error={"code": exc.code, "message": str(exc)})
            except json.JSONDecodeError as exc:
                self._response(request_id, False, error={"code": "INVALID_JSON", "message": f"Invalid JSON: {exc.msg}."})
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Sidecar request failed: %s", request_id)
                self._response(request_id, False, error={"code": "INTERNAL_ERROR", "message": "The request could not be completed."})
        self._downloads.stop()

    def dispatch(self, command: str, payload: dict[str, Any]) -> Any:
        if command == "app.bootstrap":
            return {
                "tracks": [_track_dto(track) for track in library.get_all_tracks_full()],
                "playlists": self._list_playlists(),
                "settings": _settings_dto(),
                "queue": self._downloads.snapshot(),
            }
        if command == "app.shutdown":
            return {"stopping": True}
        if command == "library.list":
            return self._list_tracks(payload)
        if command == "library.get":
            track_id = _int_id(payload.get("trackId"), "trackId")
            track = library.get_track_full(track_id)
            if track is None:
                raise SidecarError("NOT_FOUND", "Track not found.")
            return _track_dto(track, include_text=True)
        if command == "library.toggleFavorite":
            track_id = _int_id(payload.get("trackId"), "trackId")
            if library.get_track_by_id(track_id) is None:
                raise SidecarError("NOT_FOUND", "Track not found.")
            favorite = payload.get("favorite")
            if not isinstance(favorite, bool):
                raise SidecarError("INVALID_ARGUMENT", "favorite must be true or false.")
            library.update_favorite(track_id, favorite)
            return {"trackId": track_id, "favorite": favorite}
        if command == "library.delete":
            return self._delete_track(_int_id(payload.get("trackId"), "trackId"))
        if command == "library.audioSource":
            return {"path": self._audio_source(_int_id(payload.get("trackId"), "trackId"))}
        if command == "playlist.list":
            return self._list_playlists()
        if command == "playlist.create":
            name = self._playlist_name(payload.get("name"))
            try:
                playlist_id = playlists.create_playlist(name)
            except Exception as exc:
                if "unique" in str(exc).lower():
                    raise SidecarError("CONFLICT", "A playlist with that name already exists.")
                raise
            return {"playlistId": playlist_id, "name": name}
        if command == "playlist.rename":
            playlist_id = _int_id(payload.get("playlistId"), "playlistId")
            name = self._playlist_name(payload.get("name"))
            self._require_playlist(playlist_id)
            try:
                playlists.rename_playlist(playlist_id, name)
            except Exception as exc:
                if "unique" in str(exc).lower():
                    raise SidecarError("CONFLICT", "A playlist with that name already exists.")
                raise
            return {"playlistId": playlist_id, "name": name}
        if command == "playlist.delete":
            playlist_id = _int_id(payload.get("playlistId"), "playlistId")
            self._require_playlist(playlist_id)
            playlists.delete_playlist(playlist_id)
            return {"playlistId": playlist_id, "deleted": True}
        if command == "playlist.addTrack":
            playlist_id = _int_id(payload.get("playlistId"), "playlistId")
            track_id = _int_id(payload.get("trackId"), "trackId")
            self._require_playlist(playlist_id)
            if library.get_track_by_id(track_id) is None:
                raise SidecarError("NOT_FOUND", "Track not found.")
            if not playlists.is_track_in_playlist(playlist_id, track_id):
                playlists.add_track_to_playlist(playlist_id, track_id)
            return {"playlistId": playlist_id, "trackId": track_id, "added": True}
        if command == "playlist.removeTrack":
            playlist_id = _int_id(payload.get("playlistId"), "playlistId")
            track_id = _int_id(payload.get("trackId"), "trackId")
            self._require_playlist(playlist_id)
            playlists.remove_track_from_playlist(playlist_id, track_id)
            return {"playlistId": playlist_id, "trackId": track_id, "removed": True}
        if command == "downloads.snapshot":
            return self._downloads.snapshot()
        if command == "downloads.enqueue":
            urls = payload.get("urls")
            if not isinstance(urls, list):
                raise SidecarError("INVALID_ARGUMENT", "urls must be a list of strings.")
            if any(not isinstance(url, str) for url in urls):
                raise SidecarError("INVALID_ARGUMENT", "Every URL must be text.")
            format_type = payload.get("formatType", "mp3")
            if format_type not in {"mp3", "wav"}:
                raise SidecarError("INVALID_ARGUMENT", "formatType must be 'mp3' or 'wav'.")
            accepted, rejected = self._filter_youtube_urls(urls)
            if not accepted:
                if not rejected:
                    raise SidecarError("INVALID_ARGUMENT", "Add at least one YouTube URL.")
                return {"jobs": [], "failedInputs": rejected}
            result = self._downloads.enqueue_inputs(accepted, format_type)
            result["failedInputs"] = rejected + result["failedInputs"]
            return result
        if command == "settings.get":
            return _settings_dto()
        if command == "settings.update":
            return self._update_settings(payload.get("values"))
        raise SidecarError("UNKNOWN_COMMAND", f"Unknown command: {command}.")

    def _list_tracks(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_playlist_id = payload.get("playlistId")
        playlist_id = None if raw_playlist_id in (None, "") else _int_id(raw_playlist_id, "playlistId")
        if playlist_id is None:
            tracks = library.get_all_tracks_full()
        else:
            self._require_playlist(playlist_id)
            ordered_ids = [track.id for track in playlists.get_playlist_tracks(playlist_id)]
            full_by_id = {track.id: track for track in library.get_all_tracks_full()}
            tracks = [full_by_id[track_id] for track_id in ordered_ids if track_id in full_by_id]

        query = payload.get("query", "")
        if not isinstance(query, str):
            raise SidecarError("INVALID_ARGUMENT", "query must be text.")
        needle = query.strip().casefold()
        if needle:
            tracks = [
                track for track in tracks
                if needle in track.title.casefold() or needle in track.artist.casefold()
            ]

        favorites_only = payload.get("favoritesOnly", False)
        if not isinstance(favorites_only, bool):
            raise SidecarError("INVALID_ARGUMENT", "favoritesOnly must be true or false.")
        if favorites_only:
            tracks = [track for track in tracks if track.favorite]
        return [_track_dto(track) for track in tracks]

    def _list_playlists(self) -> list[dict[str, Any]]:
        from core.database import get_connection

        conn = get_connection()
        try:
            counts = {
                int(row["playlist_id"]): int(row["track_count"])
                for row in conn.execute(
                    "SELECT playlist_id, COUNT(*) AS track_count FROM playlist_tracks GROUP BY playlist_id"
                ).fetchall()
            }
        finally:
            conn.close()
        return [
            _playlist_dto(playlist, counts.get(playlist.id, 0))
            for playlist in playlists.get_all_playlists()
        ]

    def _require_playlist(self, playlist_id: int) -> Playlist:
        playlist = next(
            (item for item in playlists.get_all_playlists() if item.id == playlist_id),
            None,
        )
        if playlist is None:
            raise SidecarError("NOT_FOUND", "Playlist not found.")
        return playlist

    @staticmethod
    def _playlist_name(value: Any) -> str:
        if not isinstance(value, str):
            raise SidecarError("INVALID_ARGUMENT", "Playlist name must be text.")
        name = value.strip()
        if not name:
            raise SidecarError("INVALID_ARGUMENT", "Playlist name cannot be empty.")
        if len(name) > 80:
            raise SidecarError("INVALID_ARGUMENT", "Playlist names can contain up to 80 characters.")
        return name

    def _delete_track(self, track_id: int) -> dict[str, Any]:
        track = library.get_track_by_id(track_id)
        if track is None:
            raise SidecarError("NOT_FOUND", "Track not found.")
        folder = _contained_path(TRACKS_DIR, track.folder_name)
        if folder is None or folder.parent != TRACKS_DIR.resolve():
            raise SidecarError("INVALID_PATH", "The track folder is outside the library and was not removed.")
        library.delete_track(track_id)
        if folder.exists():
            try:
                shutil.rmtree(folder)
            except OSError as exc:
                raise SidecarError("DELETE_PARTIAL", f"The track record was removed, but its files could not be deleted: {exc}")
        return {"trackId": track_id, "deleted": True}

    def _audio_source(self, track_id: int) -> str:
        track = library.get_track_full(track_id)
        if track is None:
            raise SidecarError("NOT_FOUND", "Track not found.")
        folder = _contained_path(TRACKS_DIR, track.folder_name)
        if folder is None or folder.parent != TRACKS_DIR.resolve():
            raise SidecarError("INVALID_PATH", "The track folder is outside the library.")
        priority = {"mp3": 0, "wav": 1}
        for media in sorted(track.media_files, key=lambda item: priority.get(item.format_type, 99)):
            if media.format_type not in priority:
                continue
            if Path(media.file_name).name != media.file_name:
                continue
            path = _contained_path(folder, media.file_name)
            if path is None or path.suffix.lower() != f".{media.format_type}":
                continue
            if path.is_file():
                return str(path)
        raise SidecarError("AUDIO_NOT_FOUND", "No registered MP3 or WAV file is available for this track.")

    @staticmethod
    def _filter_youtube_urls(urls: list[str]) -> tuple[list[str], list[dict[str, str]]]:
        accepted: list[str] = []
        rejected: list[dict[str, str]] = []
        for raw in urls:
            value = raw.strip()
            if not value:
                continue
            try:
                parsed = urlparse(value)
                host = (parsed.hostname or "").lower().rstrip(".")
            except ValueError:
                rejected.append({
                    "url": value,
                    "message": "This URL is malformed.",
                })
                continue
            is_youtube = (
                host == "youtu.be"
                or host == "youtube.com"
                or host.endswith(".youtube.com")
            )
            if parsed.scheme in {"http", "https"} and is_youtube and not parsed.username and not parsed.password:
                accepted.append(value)
            else:
                rejected.append({
                    "url": value,
                    "message": "Only YouTube video and playlist URLs are supported.",
                })
        return accepted, rejected

    def _update_settings(self, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise SidecarError("INVALID_ARGUMENT", "values must be an object.")
        mapping = {
            "theme": ("theme", lambda value: value if value in {"dark", "light"} else None),
            "volume": ("volume", self._volume_value),
            "downloadQueueMode": ("download_queue_mode", lambda value: value if value in {"fifo", "parallel"} else None),
            "downloadParallelWorkers": ("download_parallel_workers", self._worker_count),
            "lyricsParallelWithDownload": ("lyrics_parallel_with_download", lambda value: value if isinstance(value, bool) else None),
        }
        for key, value in values.items():
            if key not in mapping:
                raise SidecarError("INVALID_ARGUMENT", f"Unknown setting: {key}.")
            storage_key, normalize = mapping[key]
            normalized = normalize(value)
            if normalized is None:
                raise SidecarError("INVALID_ARGUMENT", f"Invalid value for {key}.")
            set_value(storage_key, str(normalized) if key == "volume" else normalized)
        return _settings_dto()

    @staticmethod
    def _volume_value(value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        return normalized if 0 <= normalized <= 100 else None

    @staticmethod
    def _worker_count(value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        return normalized if 2 <= normalized <= 8 else None


def main() -> None:
    init_db()
    SidecarServer().serve()


if __name__ == "__main__":
    main()
