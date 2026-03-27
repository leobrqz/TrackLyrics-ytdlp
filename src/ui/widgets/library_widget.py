"""
ui/widgets/library_widget.py
Displays all tracks from the library with search/filter, favorites, and selection.
Emits track_selected when the user clicks a row.
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QVBoxLayout, QWidget, QPushButton,
)

import core.library as library
from core.models import Track


def _format_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


class LibraryWidget(QWidget):
    track_selected = Signal(object)       # Track
    request_add_to_playlist = Signal(object)  # Track, triggers context menu logic

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_tracks: list[Track] = []
        self._filtered_tracks: list[Track] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Search bar ───────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setContentsMargins(8, 8, 8, 6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search artist or title…")
        self._search.setObjectName("librarySearch")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search)
        layout.addLayout(search_row)

        # ── Track list ───────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setObjectName("libraryList")
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setSpacing(2)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list, stretch=1)

    # ── Public API ──────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload all tracks from DB and re-render."""
        self._all_tracks = library.get_all_tracks_full()
        self._apply_filter()

    def set_tracks(self, tracks: list[Track]) -> None:
        """Override displayed tracks (e.g. playlist filtered view)."""
        self._filtered_tracks = tracks
        self._render(tracks)

    # ── Internal ────────────────────────────────────────────────────────────

    def _apply_filter(self) -> None:
        query = self._search.text().strip().lower()
        if query:
            self._filtered_tracks = [
                t for t in self._all_tracks
                if query in t.title.lower() or query in t.artist.lower()
            ]
        else:
            self._filtered_tracks = list(self._all_tracks)
        self._render(self._filtered_tracks)

    def _render(self, tracks: list[Track]) -> None:
        self._list.clear()
        for track in tracks:
            fav = "★" if track.favorite else "☆"
            fmt_list = ", ".join(
                mf.format_type.upper() for mf in track.media_files
            ) if track.media_files else "?"
            dur = _format_duration(track.duration)
            label = f"{fav}  {track.artist} — {track.title}  [{fmt_list}]  {dur}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, track)
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        track: Track = item.data(Qt.ItemDataRole.UserRole)
        # Toggle favorite on star click would require a delegate; for now emit selection
        self.track_selected.emit(track)

    def _on_context_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu
        item = self._list.itemAt(pos)
        if not item:
            return
        track: Track = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        fav_label = "Remove from Favorites" if track.favorite else "Add to Favorites"
        fav_action = menu.addAction(fav_label)
        add_pl_action = menu.addAction("Add to Playlist…")
        menu.addSeparator()
        del_action = menu.addAction("Delete Track")

        action = menu.exec(self._list.mapToGlobal(pos))
        if action == fav_action:
            library.update_favorite(track.id, not track.favorite)
            self.refresh()
        elif action == add_pl_action:
            self.request_add_to_playlist.emit(track)
        elif action == del_action:
            self._delete_track(track)

    def _delete_track(self, track: Track) -> None:
        import shutil
        from utils.paths import TRACKS_DIR
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Delete Track",
            f"Delete '{track.title}' by {track.artist}?\nAll files will be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            folder = TRACKS_DIR / track.folder_name
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            library.delete_track(track.id)
            self.refresh()
