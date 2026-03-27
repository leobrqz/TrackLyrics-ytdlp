"""
ui/widgets/progress_widget.py
Download queue panel with a header row that stays visible so the queue can
always be reopened after collapsing the job list.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from download.queue import DownloadQueue

_STATUS_ICON = {
    "pending": "○",
    "running": "●",
    "done": "✓",
    "failed": "✗",
}

_STATUS_COLOR = {
    "pending": "#888888",
    "running": "#4fc3f7",
    "done": "#66bb6a",
    "failed": "#ef5350",
}


class ProgressWidget(QWidget):
    def __init__(self, queue: DownloadQueue, parent=None) -> None:
        super().__init__(parent)
        self._queue = queue
        self.setObjectName("progressWidget")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header always visible: title + show/hide (not inside collapsible frame)
        self._queue_header = QWidget()
        self._queue_header.setObjectName("queueHeaderRow")
        self._queue_header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hdr = QHBoxLayout(self._queue_header)
        hdr.setContentsMargins(10, 6, 10, 4)
        hdr.setSpacing(8)

        self._header_label = QLabel("Queue (0 jobs)")
        self._header_label.setObjectName("queueHeaderLabel")

        self._toggle_btn = QPushButton("Show queue")
        self._toggle_btn.setObjectName("queueToggleBtn")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._toggle_btn.clicked.connect(self._toggle_list)

        hdr.addWidget(self._header_label, stretch=1)
        hdr.addWidget(self._toggle_btn)
        root.addWidget(self._queue_header)

        # Collapsible: job list only
        self._list_frame = QFrame()
        self._list_frame.setObjectName("queueListFrame")
        list_layout = QVBoxLayout(self._list_frame)
        list_layout.setContentsMargins(6, 4, 6, 6)
        list_layout.setSpacing(0)

        self._job_list = QListWidget()
        self._job_list.setObjectName("jobListWidget")
        self._job_list.setMaximumHeight(120)
        self._job_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._job_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        list_layout.addWidget(self._job_list)

        root.addWidget(self._list_frame)

        strip = QFrame()
        strip.setObjectName("progressStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(10, 6, 10, 6)
        strip_layout.setSpacing(12)

        self._status_label = QLabel("Idle")
        self._status_label.setObjectName("progressTrackLabel")

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(220)
        self._progress_bar.setObjectName("downloadProgressBar")

        self._pending_label = QLabel("")
        self._pending_label.setObjectName("pendingLabel")

        strip_layout.addWidget(self._status_label, stretch=1)
        strip_layout.addWidget(self._progress_bar)
        strip_layout.addWidget(self._pending_label)

        root.addWidget(strip)

        self._list_frame.hide()
        self._toggle_btn.setText("Show queue")

    def on_progress_updated(self, job_id: str, percent: int) -> None:
        self._progress_bar.setValue(percent)
        self._refresh_list()

    def on_status_changed(self, job_id: str, status: str) -> None:
        self._status_label.setText(status)
        if status in ("Done", "Idle") or status.startswith("Failed"):
            self._progress_bar.setValue(0)
            if status in ("Done",):
                self._status_label.setText("Idle")
        self._refresh_list()

    def on_job_added(self) -> None:
        self._refresh_list()
        self._list_frame.show()
        self._toggle_btn.setText("Hide")

    def expand_queue(self) -> None:
        """Show the job list (toolbar / menu entry)."""
        self._list_frame.show()
        self._toggle_btn.setText("Hide")

    def _refresh_list(self) -> None:
        jobs = self._queue.all_jobs()
        pending = sum(1 for j in jobs if j.status == "pending")

        self._header_label.setText(f"Queue ({len(jobs)} job{'s' if len(jobs) != 1 else ''})")
        if pending > 0:
            self._pending_label.setText(f"+{pending} pending")
        else:
            self._pending_label.setText("")

        self._job_list.clear()
        for job in reversed(jobs):
            icon = _STATUS_ICON.get(job.status, "?")
            color = _STATUS_COLOR.get(job.status, "#888888")
            url_display = job.url if len(job.url) <= 55 else job.url[:52] + "…"
            text = f"  {icon}  {job.status.capitalize():<8}  {url_display}  [{job.format_type}]"
            if job.error:
                text += f"  ⚠ {job.error[:40]}"

            item = QListWidgetItem(text)
            item.setForeground(QColor(color))
            self._job_list.addItem(item)

    def _toggle_list(self) -> None:
        show = not self._list_frame.isVisible()
        self._list_frame.setVisible(show)
        self._toggle_btn.setText("Hide" if show else "Show queue")
