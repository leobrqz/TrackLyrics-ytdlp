"""
ui/dialogs/add_to_playlist_dialog.py
Modal for choosing a playlist to add a track to (styled by app theme).
"""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ui.delegates.combo_popup_delegate import ComboPopupDelegate


class AddToPlaylistDialog(QDialog):
    def __init__(self, playlist_names: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("addToPlaylistDialog")
        self.setWindowTitle("Add to Playlist")
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Choose playlist:"))

        self._combo = QComboBox()
        self._combo.addItems(playlist_names)
        self._combo.setItemDelegate(ComboPopupDelegate(self._combo))
        layout.addWidget(self._combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_playlist_name(self) -> str:
        return self._combo.currentText().strip()
