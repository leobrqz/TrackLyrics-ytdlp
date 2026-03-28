"""
ui/dialogs/settings_dialog.py
Application preferences: download queue mode and parallel lyrics option.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from core.settings import (
    get_download_parallel_workers,
    get_download_queue_mode,
    get_lyrics_parallel_with_download,
    set_value,
)
from ui.delegates.combo_popup_delegate import ComboPopupDelegate


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self._mode = QComboBox()
        self._mode.setItemDelegate(ComboPopupDelegate(self._mode))
        self._mode.addItem("FIFO (one at a time)", "fifo")
        self._mode.addItem("Parallel downloads", "parallel")
        mode = get_download_queue_mode()
        idx = 1 if mode == "parallel" else 0
        self._mode.setCurrentIndex(idx)
        self._mode.currentIndexChanged.connect(self._sync_parallel_controls)
        form.addRow("Download queue:", self._mode)

        self._workers = QSpinBox()
        self._workers.setRange(2, 8)
        self._workers.setValue(get_download_parallel_workers())
        form.addRow("Parallel workers:", self._workers)

        self._lyrics_parallel = QCheckBox("Use the same parallelism for lyrics scraping")
        self._lyrics_parallel.setChecked(get_lyrics_parallel_with_download())
        form.addRow("", self._lyrics_parallel)

        layout.addLayout(form)
        hint = QLabel(
            "Parallel mode runs several yt-dlp downloads at once; library saves stay "
            "ordered per job. Lyrics run after each batch when parallel lyrics is off."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._sync_parallel_controls()

    def _sync_parallel_controls(self) -> None:
        parallel = self._mode.currentData() == "parallel"
        self._workers.setEnabled(parallel)
        self._lyrics_parallel.setEnabled(parallel)

    def _save_and_accept(self) -> None:
        mode = self._mode.currentData()
        set_value("download_queue_mode", mode)
        set_value("download_parallel_workers", int(self._workers.value()))
        set_value("lyrics_parallel_with_download", self._lyrics_parallel.isChecked())
        self.accept()
