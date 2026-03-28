"""
ui/dialogs/track_metadata_dialog.py
Read-only track details: source URL, lyrics URLs, paths, media technical info.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import core.library as library
from core.models import Track
from core.settings import get_setting
from ui.app_style import get_metadata_link_hex
from utils.media_probe import describe_audio_file
from utils.paths import TRACKS_DIR


def _format_duration(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _dash_if_empty(s: str | None) -> str:
    t = (s or "").strip()
    return t if t else "—"


def _link_label(url: str) -> QLabel:
    lab = QLabel()
    u = url.strip()
    if not u:
        lab.setText("—")
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lab
    safe = u.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lab.setObjectName("metadataLinkLabel")
    th = get_setting("theme", "dark") or "dark"
    if th not in ("dark", "light"):
        th = "dark"
    link_color = get_metadata_link_hex(th)
    lab.setText(
        f'<a href="{safe}" style="color: {link_color}; text-decoration: underline;">{safe}</a>'
    )
    lab.setOpenExternalLinks(True)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(
        Qt.TextInteractionFlag.LinksAccessibleByMouse
        | Qt.TextInteractionFlag.TextSelectableByMouse
    )
    return lab


def _path_field(absolute: Path) -> QLineEdit:
    edit = QLineEdit(str(absolute.resolve()))
    edit.setObjectName("metadataPathEdit")
    edit.setReadOnly(True)
    edit.setFrame(True)
    return edit


def _caption(text: str) -> QLabel:
    w = QLabel(text)
    w.setObjectName("metadataCaptionLabel")
    return w


def _section_title(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("metadataSectionTitle")
    return lab


def _hline() -> QFrame:
    line = QFrame()
    line.setObjectName("metadataHLine")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setFixedHeight(1)
    return line


class TrackMetadataDialog(QDialog):
    def __init__(self, track: Track, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("trackMetadataDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Track metadata")
        self.setMinimumSize(520, 420)
        self.resize(640, 520)

        full = library.get_track_full(track.id)
        if full is None:
            full = track
        self._track = full

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("trackMetadataScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.viewport().setObjectName("trackMetadataScrollViewport")
        scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        body = QWidget()
        body.setObjectName("trackMetadataBody")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(10)
        body_layout.setContentsMargins(0, 0, 16, 16)

        t = self._track
        folder = TRACKS_DIR / t.folder_name

        body_layout.addWidget(_section_title("Track"))
        body_layout.addLayout(self._pair("Title", t.title))
        body_layout.addLayout(self._pair("Artist", t.artist))
        body_layout.addLayout(self._pair("Duration", _format_duration(t.duration)))
        body_layout.addLayout(self._pair("Added", _dash_if_empty(t.created_at)))
        body_layout.addLayout(self._pair("Favorite", "Yes" if t.favorite else "No"))
        body_layout.addLayout(self._pair("Database ID", str(t.id)))

        body_layout.addWidget(_hline())
        body_layout.addWidget(_section_title("Source"))
        src = _dash_if_empty(t.source_url)
        body_layout.addWidget(_caption("YouTube / source URL"))
        body_layout.addWidget(_link_label(src))

        body_layout.addWidget(_hline())
        body_layout.addWidget(_section_title("Library location"))
        body_layout.addWidget(_caption("Track folder"))
        body_layout.addWidget(_path_field(folder))

        body_layout.addWidget(_hline())
        body_layout.addWidget(_section_title("Media files"))
        if not t.media_files:
            body_layout.addWidget(QLabel("No media files registered."))
        else:
            for mf in t.media_files:
                abs_path = folder / mf.file_name
                cap = QLabel(f"{mf.file_name}  ({mf.format_type.upper()})")
                cap.setObjectName("metadataFileTitle")
                body_layout.addWidget(cap)
                body_layout.addWidget(_caption("File path"))
                body_layout.addWidget(_path_field(abs_path))
                body_layout.addLayout(
                    self._pair("Audio flag", "Yes" if mf.has_audio else "No"),
                )
                tech = describe_audio_file(abs_path)
                body_layout.addLayout(self._pair("File details", tech))

        body_layout.addWidget(_hline())
        body_layout.addWidget(_section_title("Lyrics"))
        ly = t.lyrics
        if ly is None:
            body_layout.addWidget(QLabel("No lyrics row in database."))
        else:
            body_layout.addWidget(_caption("Original (letras.mus.br)"))
            body_layout.addWidget(_link_label(_dash_if_empty(ly.original_url)))
            body_layout.addWidget(_caption("Translation (PT-BR)"))
            body_layout.addWidget(_link_label(_dash_if_empty(ly.ptbr_url)))
            o_path = (
                folder / ly.original_path
                if ly.original_path
                else None
            )
            p_path = folder / ly.ptbr_path if ly.ptbr_path else None
            if o_path:
                body_layout.addWidget(_caption("Original lyrics file"))
                body_layout.addWidget(_path_field(o_path))
            else:
                body_layout.addLayout(self._pair("Original lyrics file", "—"))
            if p_path:
                body_layout.addWidget(_caption("PT-BR lyrics file"))
                body_layout.addWidget(_path_field(p_path))
            else:
                body_layout.addLayout(self._pair("PT-BR lyrics file", "—"))

        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.setObjectName("trackMetadataButtonBox")
        buttons.rejected.connect(self.reject)
        copy_btn = buttons.addButton("Copy summary", QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(self._copy_summary)

        footer = QWidget()
        footer.setObjectName("trackMetadataFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        foot_lay = QHBoxLayout(footer)
        foot_lay.setContentsMargins(14, 12, 14, 14)
        foot_lay.setSpacing(10)
        foot_lay.addStretch(1)
        foot_lay.addWidget(buttons, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(footer)

    def _pair(self, label: str, value: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        l = QLabel(label + ":")
        l.setObjectName("metadataFieldKey")
        l.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        v = QLabel(value)
        v.setWordWrap(True)
        v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(l, alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(v, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    def _copy_summary(self) -> None:
        t = self._track
        lines = [
            f"Title: {t.title}",
            f"Artist: {t.artist}",
            f"Duration: {_format_duration(t.duration)}",
            f"Source URL: {_dash_if_empty(t.source_url)}",
            f"Folder: {TRACKS_DIR / t.folder_name}",
        ]
        for mf in t.media_files:
            p = TRACKS_DIR / t.folder_name / mf.file_name
            lines.append(f"Media: {mf.file_name} ({mf.format_type}) — {describe_audio_file(p)}")
        if t.lyrics:
            lines.append(f"Lyrics original URL: {_dash_if_empty(t.lyrics.original_url)}")
            lines.append(f"Lyrics PT-BR URL: {_dash_if_empty(t.lyrics.ptbr_url)}")
        text = "\n".join(lines)
        QGuiApplication.clipboard().setText(text)
