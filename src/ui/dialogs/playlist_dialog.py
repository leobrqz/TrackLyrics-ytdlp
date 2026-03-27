"""
ui/dialogs/playlist_dialog.py
Simple input dialog for creating or renaming a playlist.
"""
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout,
)


class PlaylistDialog(QDialog):
    def __init__(self, title: str = "New Playlist", initial: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Playlist name:"))

        self._name_input = QLineEdit(initial)
        self._name_input.setPlaceholderText("My Playlist")
        layout.addWidget(self._name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_name(self) -> str:
        return self._name_input.text().strip()
