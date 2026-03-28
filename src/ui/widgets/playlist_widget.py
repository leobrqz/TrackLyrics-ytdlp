"""
ui/widgets/playlist_widget.py
Left-side panel listing playlists.
Emits playlist_selected when user clicks one, or all_tracks_selected for the special entry.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import core.playlist_manager as pm

_ALL_TRACKS_ID = -1


class PlaylistWidget(QWidget):
    playlist_selected = Signal(int)
    all_tracks_selected = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("playlistWidget")
        self.setMinimumWidth(120)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(4, 6, 4, 4)
        title = QLabel("Playlists")
        title.setObjectName("playlistTitle")
        new_btn = QPushButton("+")
        new_btn.setObjectName("playlistAddBtn")
        new_btn.setToolTip("New playlist")
        new_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._on_new_playlist)
        header.addWidget(title, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(
            new_btn,
            alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        layout.addLayout(header)

        self._list = QListWidget()
        self._list.setObjectName("playlistList")
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        all_item = QListWidgetItem("All tracks")
        all_item.setData(Qt.ItemDataRole.UserRole, _ALL_TRACKS_ID)
        self._list.addItem(all_item)

        for playlist in pm.get_all_playlists():
            item = QListWidgetItem(f"  {playlist.name}")
            item.setData(Qt.ItemDataRole.UserRole, playlist.id)
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        playlist_id: int = item.data(Qt.ItemDataRole.UserRole)
        if playlist_id == _ALL_TRACKS_ID:
            self.all_tracks_selected.emit()
        else:
            self.playlist_selected.emit(playlist_id)

    def _on_new_playlist(self) -> None:
        from ui.dialogs.playlist_dialog import PlaylistDialog

        dlg = PlaylistDialog(parent=self)
        if dlg.exec() and dlg.get_name():
            pm.create_playlist(dlg.get_name())
            self.refresh()

    def _on_context_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu

        item = self._list.itemAt(pos)
        if not item:
            return
        playlist_id: int = item.data(Qt.ItemDataRole.UserRole)
        if playlist_id == _ALL_TRACKS_ID:
            return

        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self._list.mapToGlobal(pos))

        if action == rename_action:
            from ui.dialogs.playlist_dialog import PlaylistDialog

            dlg = PlaylistDialog(
                title="Rename Playlist", initial=item.text().strip(), parent=self
            )
            if dlg.exec() and dlg.get_name():
                pm.rename_playlist(playlist_id, dlg.get_name())
                self.refresh()
        elif action == delete_action:
            pm.delete_playlist(playlist_id)
            self.refresh()
            self.all_tracks_selected.emit()
