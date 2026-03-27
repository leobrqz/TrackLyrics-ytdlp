"""
player/playback_manager.py
Routes playback between AudioPlayer and VideoPlayer based on format.
Manages a playback queue for sequential playback and gapless transitions.
All interactions must occur on the main thread.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from core.models import MediaFile, Track
from player.audio_player import AudioPlayer
from player.video_player import VideoPlayer
from utils.logger import get_logger
from utils.paths import TRACKS_DIR

log = get_logger(__name__)

AUDIO_FORMATS = {"mp3", "wav"}
VIDEO_FORMATS = {"mp4"}


class PlaybackManager(QObject):
    # ── Signals forwarded to UI ─────────────────────────────────────────────
    position_changed  = Signal(int)    # ms
    duration_changed  = Signal(int)    # ms
    track_changed     = Signal(object) # Track currently playing
    playback_finished = Signal()
    error_occurred    = Signal(str)
    video_visible     = Signal(bool)   # True when video widget should be shown

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._audio = AudioPlayer(self)
        self._video = VideoPlayer(self)

        self._tracks: list[Track] = []       # current playback queue
        self._current_index: int = -1
        self._active: Optional[str] = None   # 'audio' | 'video'
        self._volume: float = 0.8

        # Wire sub-player signals
        for player in (self._audio, self._video):
            player.position_changed.connect(self.position_changed)
            player.duration_changed.connect(self.duration_changed)
            player.playback_finished.connect(self._on_track_finished)
            player.error_occurred.connect(self._on_player_error)

    # ── Queue management ────────────────────────────────────────────────────

    def set_queue(self, tracks: list[Track], start_index: int = 0) -> None:
        """Set the playback queue and immediately start playing at start_index."""
        self._tracks = tracks
        self._play_at(start_index)

    def next_track(self) -> None:
        if self._current_index < len(self._tracks) - 1:
            self._play_at(self._current_index + 1)

    def prev_track(self) -> None:
        if self._current_index > 0:
            self._play_at(self._current_index - 1)

    def current_track(self) -> Optional[Track]:
        if 0 <= self._current_index < len(self._tracks):
            return self._tracks[self._current_index]
        return None

    # ── Playback controls ───────────────────────────────────────────────────

    def play(self) -> None:
        self._active_player().play()

    def pause(self) -> None:
        self._active_player().pause()

    def seek(self, ms: int) -> None:
        self._active_player().seek(ms)

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 – 1.0"""
        self._volume = volume
        self._audio.set_volume(volume)
        self._video.set_volume(volume)

    def get_video_widget(self):
        return self._video.get_video_widget()

    # ── Internal ────────────────────────────────────────────────────────────

    def _play_at(self, index: int) -> None:
        if not self._tracks or not (0 <= index < len(self._tracks)):
            return

        self._stop_all()
        self._current_index = index
        track = self._tracks[index]

        # Lazy-load media_files if not already populated.
        # Tracks fetched via playlist queries don't carry media_files.
        if not track.media_files:
            import core.library as library  # local import to avoid circular dep
            track.media_files = library.get_media_files(track.id)

        media_file = self._pick_media_file(track)
        if media_file is None:
            self.error_occurred.emit(
                f"No playable media file found for: {track.title}"
            )
            return

        file_path = TRACKS_DIR / track.folder_name / media_file.file_name
        if not file_path.exists():
            self.error_occurred.emit(
                f"Media file missing on disk: {file_path.name}"
            )
            return

        fmt = media_file.format_type
        if fmt in AUDIO_FORMATS:
            self._active = "audio"
            self.video_visible.emit(False)
            self._audio.set_source(file_path)
            self._audio.set_volume(self._volume)
            self._audio.play()
        elif fmt in VIDEO_FORMATS:
            self._active = "video"
            self.video_visible.emit(True)
            self._video.set_source(file_path)
            self._video.set_volume(self._volume)
            self._video.play()
        else:
            self.error_occurred.emit(f"Unsupported format: {fmt}")
            return

        self.track_changed.emit(track)
        log.info("Playing: %s — %s  [%s]", track.artist, track.title, fmt)

    def _stop_all(self) -> None:
        self._audio.stop()
        self._video.stop()

    def _active_player(self) -> AudioPlayer | VideoPlayer:
        return self._video if self._active == "video" else self._audio

    def _pick_media_file(self, track: Track) -> Optional[MediaFile]:
        """Prefer mp3 > wav > mp4 for audio; mp4 if only video exists."""
        if not track.media_files:
            return None
        priority = {"mp3": 0, "wav": 1, "mp4": 2}
        return min(track.media_files, key=lambda mf: priority.get(mf.format_type, 99))

    def _on_track_finished(self) -> None:
        if self._current_index < len(self._tracks) - 1:
            # Gapless: immediately start next
            self._play_at(self._current_index + 1)
        else:
            self.playback_finished.emit()

    def _on_player_error(self, msg: str) -> None:
        self.error_occurred.emit(msg)
