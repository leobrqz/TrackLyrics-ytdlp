"""
ui/dialogs/duplicate_dialog.py
Non-blocking warning shown when a duplicate (artist, title) is detected.
"""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class DuplicateDialog(QDialog):
    def __init__(self, artist: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Duplicate Detected")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel(
            f"<b>{artist} — {title}</b> already exists in your library.<br>"
            "It will be saved as a new entry anyway."
        ))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
