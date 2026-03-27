"""
ui/dialogs/download_dialog.py
Modal for submitting YouTube URLs and choosing a download format.
"""
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel,
    QPlainTextEdit, QVBoxLayout,
)


class DownloadDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("downloadDialog")
        self.setWindowTitle("Add Downloads")
        self.setMinimumWidth(500)
        self.setMinimumHeight(260)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("YouTube URL(s) — one per line:"))

        self._url_input = QPlainTextEdit()
        self._url_input.setPlaceholderText(
            "https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=..."
        )
        layout.addWidget(self._url_input)

        layout.addWidget(QLabel("Format:"))
        self._format_box = QComboBox()
        self._format_box.addItems(["mp3", "mp4", "wav"])
        layout.addWidget(self._format_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_urls(self) -> list[str]:
        raw = self._url_input.toPlainText()
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def get_format(self) -> str:
        return self._format_box.currentText()
