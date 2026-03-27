"""
player/playback_manager.py
Audio-only playback via AudioPlayer (mp3, wav).
Manages a playback queue for sequential playback and gapless transitions.
All interactions must occur on the main thread.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from core.models import MediaFile, Track
from player.audio_player import AudioPlayer
from utils.logger import get_logger
from utils.paths import TRACKS_DIR

log = get_logger(__name__)

AUDIO_FORMATS = {"mp3", "wav"}


class PlaybackManager(QObject):
    position_changed = Signal(int)    # ms
    duration_changed = Signal(int)    # ms
    track_changed = Signal(object)    # Track currently playing
    playback_finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._audio = AudioPlayer(self)
        self._tracks: list[Track] = []
        self._current_index: int = -1
        self._volume: float = 0.8

        self._audio.position_changed.connect(self.position_changed)
        self._audio.duration_changed.connect(self.duration_changed)
        self._audio.playback_finished.connect(self._on_track_finished)
        self._audio.error_occurred.connect(self._on_player_error)

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

    def play(self) -> None:
        self._audio.play()

    def pause(self) -> None:
        self._audio.pause()

    def seek(self, ms: int) -> None:
        self._audio.seek(ms)

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 – 1.0"""
        self._volume = volume
        self._audio.set_volume(volume)

    def is_playing(self) -> bool:
        return self._audio.is_playing()

    def _play_at(self, index: int) -> None:
        if not self._tracks or not (0 <= index < len(self._tracks)):
            return

        self._audio.stop()
        self._current_index = index
        track = self._tracks[index]

        if not track.media_files:
            import core.library as library

            track.media_files = library.get_media_files(track.id)

        media_file = self._pick_media_file(track)
        if media_file is None:
            self.error_occurred.emit(
                f"No playable audio file (mp3/wav) for: {track.title}"
            )
            return

        file_path = TRACKS_DIR / track.folder_name / media_file.file_name
        if not file_path.exists():
            self.error_occurred.emit(
                f"Media file missing on disk: {file_path.name}"
            )
            return

        fmt = media_file.format_type
        if fmt not in AUDIO_FORMATS:
            self.error_occurred.emit(f"Unsupported format: {fmt}")
            return

        self._audio.set_source(file_path)
        self._audio.set_volume(self._volume)
        self._audio.play()

        self.track_changed.emit(track)
        log.info("Playing: %s — %s  [%s]", track.artist, track.title, fmt)

    def _pick_media_file(self, track: Track) -> Optional[MediaFile]:
        """Prefer mp3 over wav."""
        playable = [mf for mf in track.media_files if mf.format_type in AUDIO_FORMATS]
        if not playable:
            return None
        priority = {"mp3": 0, "wav": 1}
        return min(playable, key=lambda mf: priority.get(mf.format_type, 99))

    def _on_track_finished(self) -> None:
        if self._current_index < len(self._tracks) - 1:
            self._play_at(self._current_index + 1)
        else:
            self.playback_finished.emit()

    def _on_player_error(self, msg: str) -> None:
        self.error_occurred.emit(msg)
