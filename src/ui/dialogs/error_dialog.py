"""
ui/dialogs/error_dialog.py
Reusable modal popup for errors and warnings.
"""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt


class ErrorDialog(QDialog):
    def __init__(
        self,
        operation: str,
        reason: str,
        hint: str = "",
        level: str = "error",   # 'error' | 'warning'
        parent=None,
    ) -> None:
        super().__init__(parent)
        title = "Error" if level == "error" else "Warning"
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        op_label = QLabel(f"<b>Operation:</b> {operation}")
        op_label.setWordWrap(True)

        reason_label = QLabel(f"<b>Reason:</b> {reason}")
        reason_label.setWordWrap(True)

        layout.addWidget(op_label)
        layout.addWidget(reason_label)

        if hint:
            hint_label = QLabel(f"<i>{hint}</i>")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
