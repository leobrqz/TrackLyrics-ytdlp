"""
ui/widgets/player_widget.py
Playback control bar: play/pause, previous, next, seek slider, volume, format label.
Also contains the QVideoWidget area (shown/hidden based on whether mp4 is playing).
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)


def _media_icons(style: QStyle) -> tuple:
    """StandardPixmap media icons when available; callers fall back to text."""
    px = QStyle.StandardPixmap
    play = getattr(px, "SP_MediaPlay", None)
    pause = getattr(px, "SP_MediaPause", None)
    back = getattr(px, "SP_MediaSkipBackward", None)
    forward = getattr(px, "SP_MediaSkipForward", None)
    icons = []
    for p in (play, pause, back, forward):
        if p is not None:
            icons.append(style.standardIcon(p))
        else:
            icons.append(None)
    return tuple(icons)


class PlayerWidget(QWidget):
    play_pause_clicked = Signal()
    prev_clicked = Signal()
    next_clicked = Signal()
    seek_requested = Signal(int)
    volume_changed = Signal(float)

    def __init__(self, video_widget: QWidget, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("playerWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        style = self.style()
        play_ic, pause_ic, back_ic, forward_ic = _media_icons(style)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(8)

        self._video_area = video_widget
        self._video_area.setMinimumHeight(0)
        self._video_area.setObjectName("videoArea")
        self._video_area.hide()
        root.addWidget(self._video_area)

        info_row = QHBoxLayout()
        self._track_label = QLabel("–")
        self._track_label.setObjectName("nowPlayingLabel")
        self._track_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._format_label = QLabel("")
        self._format_label.setObjectName("formatLabel")
        info_row.addWidget(self._track_label, stretch=1)
        info_row.addWidget(self._format_label)
        root.addLayout(info_row)

        seek_row = QHBoxLayout()
        self._position_label = QLabel("0:00")
        self._position_label.setFixedWidth(44)
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setObjectName("seekSlider")
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._duration_label = QLabel("0:00")
        self._duration_label.setFixedWidth(44)
        self._duration_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._seek_slider.sliderReleased.connect(self._on_seek)
        seek_row.addWidget(self._position_label)
        seek_row.addWidget(self._seek_slider, stretch=1)
        seek_row.addWidget(self._duration_label)
        root.addLayout(seek_row)

        self._prev_btn = QPushButton()
        self._play_btn = QPushButton()
        self._next_btn = QPushButton()
        for btn in (self._prev_btn, self._play_btn, self._next_btn):
            btn.setFixedSize(44, 44)
            btn.setObjectName("playerBtn")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        ic_size = QSize(22, 22)
        if back_ic and not back_ic.isNull():
            self._prev_btn.setIcon(back_ic)
            self._prev_btn.setIconSize(ic_size)
        else:
            self._prev_btn.setText("⏮")

        if play_ic and not play_ic.isNull():
            self._play_btn.setIcon(play_ic)
            self._play_btn.setIconSize(ic_size)
        else:
            self._play_btn.setText("▶")

        if forward_ic and not forward_ic.isNull():
            self._next_btn.setIcon(forward_ic)
            self._next_btn.setIconSize(ic_size)
        else:
            self._next_btn.setText("⏭")

        self._prev_btn.clicked.connect(self.prev_clicked)
        self._play_btn.clicked.connect(self.play_pause_clicked)
        self._next_btn.clicked.connect(self.next_clicked)

        self._transport_icons = (play_ic, pause_ic)
        self._play_fallback = "▶"
        self._pause_fallback = "⏸"

        vol_label = QLabel("Vol")
        vol_label.setObjectName("volumeLabel")
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setObjectName("volSlider")
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(100)
        self._vol_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._vol_pct = QLabel("80%")
        self._vol_pct.setObjectName("volumeLabel")
        self._vol_pct.setFixedWidth(36)
        self._vol_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def _on_volume(v: int) -> None:
            self._vol_pct.setText(f"{v}%")
            self.volume_changed.emit(v / 100.0)

        self._vol_slider.valueChanged.connect(_on_volume)

        center = QWidget()
        center_l = QHBoxLayout(center)
        center_l.setContentsMargins(0, 0, 0, 0)
        center_l.setSpacing(10)
        center_l.addWidget(self._prev_btn)
        center_l.addWidget(self._play_btn)
        center_l.addWidget(self._next_btn)

        right = QWidget()
        right_l = QHBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(8)
        right_l.addStretch(1)
        right_l.addWidget(vol_label)
        right_l.addWidget(self._vol_slider)
        right_l.addWidget(self._vol_pct)

        left_sp = QWidget()
        left_sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(0)
        ctrl_row.addWidget(left_sp, 1)
        ctrl_row.addWidget(center, 0, Qt.AlignmentFlag.AlignVCenter)
        ctrl_row.addWidget(right, 1)

        root.addLayout(ctrl_row)

        self.apply_minimum_from_layout()

    def apply_minimum_from_layout(self) -> None:
        self.updateGeometry()
        lay = self.layout()
        if lay is None:
            return
        h = lay.totalMinimumSize().height()
        self.setMinimumHeight(max(h, 120))

    def set_track_info(self, artist: str, title: str, fmt: str) -> None:
        self._track_label.setText(f"{artist} — {title}")
        self._format_label.setText(fmt.upper())

    def set_position(self, ms: int) -> None:
        if not self._seek_slider.isSliderDown():
            duration = self._duration_ms
            if duration > 0:
                self._seek_slider.setValue(int(ms / duration * 1000))
        self._position_label.setText(_fmt_time(ms))

    def set_duration(self, ms: int) -> None:
        self._duration_ms = ms
        self._duration_label.setText(_fmt_time(ms))

    def set_playing(self, playing: bool) -> None:
        pl, pa = self._transport_icons
        if pl and not pl.isNull() and pa and not pa.isNull():
            self._play_btn.setIcon(pa if playing else pl)
            self._play_btn.setText("")
        else:
            self._play_btn.setText(self._pause_fallback if playing else self._play_fallback)

    def set_video_visible(self, visible: bool) -> None:
        self._video_area.setVisible(visible)
        self._video_area.setMinimumHeight(180 if visible else 0)
        self.apply_minimum_from_layout()

    _duration_ms: int = 0

    def _on_seek(self) -> None:
        if self._duration_ms > 0:
            ms = int(self._seek_slider.value() / 1000 * self._duration_ms)
            self.seek_requested.emit(ms)


def _fmt_time(ms: int) -> str:
    total_s = ms // 1000
    m, s = divmod(total_s, 60)
    return f"{m}:{s:02d}"
