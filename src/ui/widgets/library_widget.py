"""
ui/widgets/library_widget.py
Displays all tracks from the library in a table with search/filter, favorites, and selection.
Emits track_selected when the user selects a row.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import core.library as library
from core.models import Track


def _format_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _format_formats(track: Track) -> str:
    if not track.media_files:
        return "?"
    return ", ".join(mf.format_type.upper() for mf in track.media_files)


class LibraryWidget(QWidget):
    track_selected = Signal(object)       # Track
    request_add_to_playlist = Signal(object)
    request_remove_from_playlist = Signal(object)

    _COL_FAV = 0
    _COL_ARTIST = 1
    _COL_TITLE = 2
    _COL_FORMAT = 3
    _COL_DURATION = 4

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_tracks: list[Track] = []
        self._filtered_tracks: list[Track] = []
        self._playlist_context_id: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(8, 8, 8, 6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search artist or title…")
        self._search.setObjectName("librarySearch")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search)
        layout.addLayout(search_row)

        self._table = QTableWidget(0, 5)
        self._table.setObjectName("libraryTable")
        self._table.setFrameShape(QFrame.Shape.NoFrame)
        self._table.setHorizontalHeaderLabels(
            ["", "Artist", "Title", "Format", "Time"]
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(True)
        self._table.setAlternatingRowColors(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(28)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self._COL_FAV, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self._COL_ARTIST, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self._COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self._COL_FORMAT, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self._COL_DURATION, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self._COL_FAV, 36)
        self._table.setColumnWidth(self._COL_FORMAT, 72)
        self._table.setColumnWidth(self._COL_DURATION, 56)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        self._table_wrap = QFrame()
        self._table_wrap.setObjectName("libraryTableFrame")
        wrap_lay = QVBoxLayout(self._table_wrap)
        wrap_lay.setContentsMargins(0, 0, 0, 0)
        wrap_lay.setSpacing(0)
        wrap_lay.addWidget(self._table)
        layout.addWidget(self._table_wrap, stretch=1)

    # ── Public API ──────────────────────────────────────────────────────────

    def refresh(self) -> None:
        selected_id: Optional[int] = None
        row = self._table.currentRow()
        if row >= 0:
            t = self._track_at_row(row)
            if t:
                selected_id = t.id
        self._all_tracks = library.get_all_tracks_full()
        self._apply_filter()
        if selected_id is not None:
            self.select_track_by_id(selected_id)

    def set_tracks(self, tracks: list[Track]) -> None:
        self._filtered_tracks = tracks
        self._render(tracks)

    def set_playlist_context(self, playlist_id: Optional[int]) -> None:
        self._playlist_context_id = playlist_id

    def select_track_by_id(self, track_id: int) -> bool:
        for row in range(self._table.rowCount()):
            t = self._track_at_row(row)
            if t and t.id == track_id:
                self._table.blockSignals(True)
                self._table.selectRow(row)
                self._table.blockSignals(False)
                idx = self._table.model().index(row, 0)
                self._table.scrollTo(idx, QAbstractItemView.ScrollHint.EnsureVisible)
                return True
        return False

    # ── Internal ────────────────────────────────────────────────────────────

    def _track_at_row(self, row: int) -> Optional[Track]:
        it = self._table.item(row, self._COL_FAV)
        if it is None:
            return None
        data = it.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, Track) else None

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

    def _make_row_items(self, track: Track) -> list[QTableWidgetItem]:
        fav = "★" if track.favorite else "☆"
        items = [
            QTableWidgetItem(fav),
            QTableWidgetItem(track.artist),
            QTableWidgetItem(track.title),
            QTableWidgetItem(_format_formats(track)),
            QTableWidgetItem(_format_duration(track.duration)),
        ]
        items[self._COL_FAV].setTextAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        items[self._COL_FORMAT].setTextAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        items[self._COL_DURATION].setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        non_editable = (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )
        for i, it in enumerate(items):
            it.setFlags(non_editable)
            if i == self._COL_FAV:
                it.setData(Qt.ItemDataRole.UserRole, track)
        return items

    def _render(self, tracks: list[Track]) -> None:
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        self._table.setRowCount(len(tracks))
        for row, track in enumerate(tracks):
            items = self._make_row_items(track)
            for col, it in enumerate(items):
                self._table.setItem(row, col, it)
        self._table.blockSignals(False)

    def _on_selection_changed(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        track = self._track_at_row(row)
        if track:
            self.track_selected.emit(track)

    def _on_context_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu

        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        track = self._track_at_row(idx.row())
        if not track:
            return
        menu = QMenu(self)

        fav_label = "Remove from Favorites" if track.favorite else "Add to Favorites"
        fav_action = menu.addAction(fav_label)
        add_pl_action = menu.addAction("Add to Playlist…")
        remove_pl_action = None
        if self._playlist_context_id is not None:
            remove_pl_action = menu.addAction("Remove from Playlist")
        menu.addSeparator()
        meta_action = menu.addAction("View Metadata…")
        menu.addSeparator()
        del_action = menu.addAction("Delete Track")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == fav_action:
            library.update_favorite(track.id, not track.favorite)
            self.refresh()
        elif action == add_pl_action:
            self.request_add_to_playlist.emit(track)
        elif remove_pl_action is not None and action == remove_pl_action:
            self.request_remove_from_playlist.emit(track)
        elif action == meta_action:
            from ui.dialogs.track_metadata_dialog import TrackMetadataDialog

            dlg = TrackMetadataDialog(track, parent=self.window())
            dlg.exec()
        elif action == del_action:
            self._delete_track(track)

    def _delete_track(self, track: Track) -> None:
        import shutil
        from PySide6.QtWidgets import QMessageBox

        from utils.paths import TRACKS_DIR

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
