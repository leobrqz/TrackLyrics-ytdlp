"""
ui/widgets/lyrics_widget.py
Two-tab panel showing original and PT-BR lyrics from local .md files.
Reloads when a track is selected or when lyrics_ready fires.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QLabel, QScrollArea, QTabWidget, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from core.models import Track
from utils.paths import TRACKS_DIR


class LyricsWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("lyricsWidget")
        self._current_track: Optional[Track] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("lyricsTabs")

        self._orig_label = self._make_scroll_label()
        self._ptbr_label = self._make_scroll_label()

        self._tabs.addTab(self._orig_label["scroll"], "Original")
        self._tabs.addTab(self._ptbr_label["scroll"], "PT-BR")

        layout.addWidget(self._tabs)
        self._show_placeholder(self._orig_label["label"])
        self._show_placeholder(self._ptbr_label["label"])

    # ── Public API ──────────────────────────────────────────────────────────

    def load_track(self, track: Track) -> None:
        self._current_track = track
        self._reload()

    def on_lyrics_ready(self, track_id: int) -> None:
        """Called when the worker finishes scraping a track's lyrics."""
        if self._current_track and self._current_track.id == track_id:
            # Reload the track from DB to get updated lyrics ref
            import core.library as library
            updated = library.get_track_by_id(track_id)
            if updated:
                updated.lyrics = library.get_lyrics(track_id)
                self._current_track = updated
                self._reload()

    # ── Internal ────────────────────────────────────────────────────────────

    def _reload(self) -> None:
        track = self._current_track
        if track is None:
            return

        lyrics = track.lyrics
        if lyrics is None:
            self._show_placeholder(self._orig_label["label"])
            self._show_placeholder(self._ptbr_label["label"])
            return

        if lyrics.has_original and lyrics.original_path:
            path = TRACKS_DIR / track.folder_name / lyrics.original_path
            self._load_file(path, self._orig_label["label"])
        else:
            self._show_placeholder(self._orig_label["label"])

        if lyrics.has_ptbr and lyrics.ptbr_path:
            path = TRACKS_DIR / track.folder_name / lyrics.ptbr_path
            self._load_file(path, self._ptbr_label["label"])
        else:
            self._show_placeholder(self._ptbr_label["label"], "No PT-BR translation available.")

    def _load_file(self, path: Path, label: QLabel) -> None:
        try:
            text = path.read_text(encoding="utf-8")
            label.setText(text)
            label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        except OSError:
            self._show_placeholder(label, "Lyrics file not found on disk.")

    def _show_placeholder(self, label: QLabel, msg: str = "Lyrics unavailable.") -> None:
        label.setText(msg)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def _make_scroll_label() -> dict:
        label = QLabel()
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName("lyricsLabel")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(label)
        scroll.setObjectName("lyricsScroll")
        return {"scroll": scroll, "label": label}
