"""
ui/widgets/lyrics_widget.py
Original vs PT-BR lyrics from local .md files, shown in a stacked view.

Uses QStackedWidget + tool buttons instead of QTabWidget: QTabWidget combines
QTabBar + QStackedWidget with style-engine seams; Fusion + app-level QSS often
leave a 1px line at the tab/pane junction where base-style palette shows through.
Reloads when a track is selected or when lyrics_ready fires.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from core.models import Track
from utils.paths import TRACKS_DIR


class LyricsWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("lyricsWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._current_track: Optional[Track] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        mode_row = QWidget()
        mode_row.setObjectName("lyricsModeRow")
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)

        self._btn_orig = QToolButton()
        self._btn_orig.setObjectName("lyricsTabBtnFirst")
        self._btn_orig.setText("Original")
        self._btn_orig.setCheckable(True)
        self._btn_orig.setChecked(True)
        self._btn_orig.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._btn_orig.setAutoRaise(True)
        self._btn_orig.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_orig.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_orig.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self._btn_ptbr = QToolButton()
        self._btn_ptbr.setObjectName("lyricsTabBtnSecond")
        self._btn_ptbr.setText("PT-BR")
        self._btn_ptbr.setCheckable(True)
        self._btn_ptbr.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._btn_ptbr.setAutoRaise(True)
        self._btn_ptbr.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_ptbr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ptbr.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.addButton(self._btn_orig, 0)
        self._group.addButton(self._btn_ptbr, 1)
        self._group.idClicked.connect(self._on_mode_id)

        mode_layout.addWidget(self._btn_orig, 0, Qt.AlignmentFlag.AlignLeft)
        mode_layout.addWidget(self._btn_ptbr, 0, Qt.AlignmentFlag.AlignLeft)
        mode_layout.addStretch(1)

        self._stack = QStackedWidget()
        self._stack.setObjectName("lyricsStack")

        self._orig_label = self._make_scroll_label()
        self._ptbr_label = self._make_scroll_label()

        self._stack.addWidget(self._orig_label["scroll"])
        self._stack.addWidget(self._ptbr_label["scroll"])

        layout.addWidget(mode_row)
        layout.addWidget(self._stack, stretch=1)

        self._show_placeholder(self._orig_label["label"])
        self._show_placeholder(self._ptbr_label["label"])

    def _on_mode_id(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    # ── Public API ──────────────────────────────────────────────────────────

    def load_track(self, track: Track) -> None:
        self._current_track = track
        self._reload()

    def on_lyrics_ready(self, track_id: int) -> None:
        """Called when the worker finishes scraping a track's lyrics."""
        if self._current_track and self._current_track.id == track_id:
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
