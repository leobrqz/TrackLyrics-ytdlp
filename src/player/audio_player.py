"""
player/audio_player.py
Wraps QMediaPlayer + QAudioOutput for audio-only playback (mp3, wav).
All interactions must occur on the main thread.
"""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from utils.logger import get_logger

log = get_logger(__name__)


class AudioPlayer(QObject):
    position_changed = Signal(int)   # milliseconds
    duration_changed = Signal(int)   # milliseconds
    playback_finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        # Wire internal signals — use lambdas to bridge qlonglong → int
        self._player.positionChanged.connect(lambda pos: self.position_changed.emit(int(pos)))
        self._player.durationChanged.connect(lambda dur: self.duration_changed.emit(int(dur)))
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.errorOccurred.connect(self._on_error)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_source(self, path: Path) -> None:
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        log.debug("AudioPlayer source: %s", path.name)

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, ms: int) -> None:
        self._player.setPosition(ms)

    def set_volume(self, volume: float) -> None:
        """volume: 0.0 – 1.0"""
        self._audio_output.setVolume(volume)

    def position(self) -> int:
        return self._player.position()

    def duration(self) -> int:
        return self._player.duration()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # ── Private ─────────────────────────────────────────────────────────────

    def _on_state_changed(self, state) -> None:
        if state == QMediaPlayer.PlaybackState.StoppedState:
            if self._player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.playback_finished.emit()

    def _on_error(self, error, error_string: str) -> None:
        log.error("AudioPlayer error: %s", error_string)
        self.error_occurred.emit(error_string)
