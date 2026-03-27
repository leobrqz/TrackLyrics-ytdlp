"""
ui/main_window.py
Root QMainWindow — assembles all widgets, wires all signals, manages theme,
runs startup validation, and coordinates the download worker.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import core.library as library
import core.playlist_manager as pm
from core.settings import get_setting, set_setting
from download.queue import DownloadJob, DownloadQueue
from player.playback_manager import PlaybackManager
from ui.dialogs.download_dialog import DownloadDialog
from ui.dialogs.duplicate_dialog import DuplicateDialog
from ui.dialogs.error_dialog import ErrorDialog
from ui.widgets.library_widget import LibraryWidget
from ui.widgets.lyrics_widget import LyricsWidget
from ui.widgets.player_widget import PlayerWidget
from ui.widgets.playlist_widget import PlaylistWidget
from ui.widgets.progress_widget import ProgressWidget
from worker.download_worker import DownloadWorker
from utils.paths import TRACKS_DIR
from ui.app_style import get_stylesheet


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TrackLyrics")
        self.setMinimumSize(1100, 680)

        # ── Core objects ─────────────────────────────────────────────────────
        self._queue = DownloadQueue()
        self._worker = DownloadWorker(self._queue)
        self._playback = PlaybackManager(self)

        # ── Build UI (central before toolbar: Queue action needs progress widget) ─
        self._build_central()
        self._build_toolbar()
        self._build_status_bar()

        # ── Wire signals ─────────────────────────────────────────────────────
        self._wire_worker()
        self._wire_playback()

        # ── Start worker ─────────────────────────────────────────────────────
        self._worker.start()

        # ── Apply theme ──────────────────────────────────────────────────────
        theme = get_setting("theme", "dark")
        self._apply_theme(theme)

        # ── Startup validation ───────────────────────────────────────────────
        self._validate_library()

        # ── Load initial library ─────────────────────────────────────────────
        self._library_widget.refresh()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._download_btn = QPushButton("Download")
        self._download_btn.setObjectName("toolbarPrimaryBtn")
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.setToolTip("Download tracks from YouTube")
        self._download_btn.clicked.connect(self._open_download_dialog)
        tb.addWidget(self._download_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        tb.addWidget(spacer)

        self._queue_btn = QPushButton("Queue")
        self._queue_btn.setObjectName("toolbarTextBtn")
        self._queue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._queue_btn.setToolTip("Show download queue")
        self._queue_btn.clicked.connect(self._progress_widget.expand_queue)
        tb.addWidget(self._queue_btn)

        self._theme_btn = QPushButton()
        self._theme_btn.setObjectName("toolbarTextBtn")
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(self._toggle_theme)
        tb.addWidget(self._theme_btn)

    def _build_central(self) -> None:
        central = QWidget()
        central.setObjectName("centralRoot")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 4, 8, 6)
        root.setSpacing(6)

        # ── Top: sidebar | library | lyrics ─────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")
        splitter.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        self._playlist_widget = PlaylistWidget()
        self._library_widget = LibraryWidget()
        self._lyrics_widget = LyricsWidget()

        splitter.addWidget(self._playlist_widget)
        splitter.addWidget(self._library_widget)
        splitter.addWidget(self._lyrics_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        root.addWidget(splitter, stretch=1)

        # ── Bottom: player controls ──────────────────────────────────────────
        self._player_widget = PlayerWidget(
            video_widget=self._playback.get_video_widget()
        )
        root.addWidget(self._player_widget)

        # ── Progress bar ─────────────────────────────────────────────────────
        self._progress_widget = ProgressWidget(queue=self._queue)
        root.addWidget(self._progress_widget)

        # ── Playlist ↔ library wiring ────────────────────────────────────────
        self._playlist_widget.all_tracks_selected.connect(self._library_widget.refresh)
        self._playlist_widget.playlist_selected.connect(self._on_playlist_selected)
        self._library_widget.track_selected.connect(self._on_track_selected)
        self._library_widget.request_add_to_playlist.connect(self._on_add_to_playlist)

    def _build_status_bar(self) -> None:
        self.setStatusBar(QStatusBar())

    # ── Signal wiring ────────────────────────────────────────────────────────

    def _wire_worker(self) -> None:
        w = self._worker
        w.progress_updated.connect(self._progress_widget.on_progress_updated)
        w.status_changed.connect(self._progress_widget.on_status_changed)
        w.track_saved.connect(self._on_track_saved)
        w.lyrics_ready.connect(self._lyrics_widget.on_lyrics_ready)
        w.duplicate_detected.connect(self._on_duplicate)
        w.error_occurred.connect(self._on_error)

    def _wire_playback(self) -> None:
        pm = self._playback
        pm.position_changed.connect(self._player_widget.set_position)
        pm.duration_changed.connect(self._player_widget.set_duration)
        pm.video_visible.connect(self._player_widget.set_video_visible)
        pm.error_occurred.connect(
            lambda msg: self._on_error("Playback Error", msg, "Try selecting another format.")
        )
        pm.track_changed.connect(self._on_playback_track_changed)

        pw = self._player_widget
        pw.play_pause_clicked.connect(self._toggle_play)
        pw.prev_clicked.connect(self._playback.prev_track)
        pw.next_clicked.connect(self._playback.next_track)
        pw.seek_requested.connect(self._playback.seek)
        pw.volume_changed.connect(self._playback.set_volume)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _open_download_dialog(self) -> None:
        dlg = DownloadDialog(self)
        if dlg.exec():
            urls = dlg.get_urls()
            fmt = dlg.get_format()
            for url in urls:
                self._queue.add(DownloadJob(url=url, format_type=fmt))
            self._progress_widget.on_job_added()

    def _on_track_saved(self, track_id: int) -> None:
        self._library_widget.refresh()

    def _on_track_selected(self, track) -> None:
        self._lyrics_widget.load_track(track)
        # Build queue from current library view and start playing
        tracks = self._library_widget._filtered_tracks
        try:
            idx = next(i for i, t in enumerate(tracks) if t.id == track.id)
        except StopIteration:
            idx = 0
        self._playback.set_queue(tracks, start_index=idx)

    def _on_playback_track_changed(self, track) -> None:
        self._player_widget.set_track_info(
            track.artist, track.title,
            track.media_files[0].format_type if track.media_files else "?"
        )
        self._player_widget.set_playing(True)

    def _toggle_play(self) -> None:
        from player.audio_player import AudioPlayer
        active = self._playback._active_player()
        if active.is_playing():
            self._playback.pause()
            self._player_widget.set_playing(False)
        else:
            self._playback.play()
            self._player_widget.set_playing(True)

    def _on_playlist_selected(self, playlist_id: int) -> None:
        tracks = pm.get_playlist_tracks(playlist_id)
        self._library_widget.set_tracks(tracks)

    def _on_add_to_playlist(self, track) -> None:
        playlists = pm.get_all_playlists()
        if not playlists:
            QMessageBox.information(self, "No Playlists", "Create a playlist first.")
            return
        from PySide6.QtWidgets import QInputDialog
        names = [p.name for p in playlists]
        name, ok = QInputDialog.getItem(
            self, "Add to Playlist", "Choose playlist:", names, editable=False
        )
        if ok and name:
            playlist = next(p for p in playlists if p.name == name)
            pm.add_track_to_playlist(playlist.id, track.id)

    def _on_duplicate(self, artist: str, title: str) -> None:
        dlg = DuplicateDialog(artist, title, self)
        dlg.exec()

    def _on_error(self, operation: str, reason: str, hint: str) -> None:
        lvl = "warning" if "lyrics" in operation.lower() or "duplicate" in operation.lower() \
              else "error"
        dlg = ErrorDialog(operation, reason, hint, level=lvl, parent=self)
        dlg.exec()

    # ── Theme ────────────────────────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        current = get_setting("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        set_setting("theme", new_theme)
        self._apply_theme(new_theme)

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(get_stylesheet(theme))
        if theme == "dark":
            self._theme_btn.setText("Light")
            self._theme_btn.setToolTip("Switch to light theme")
        else:
            self._theme_btn.setText("Dark")
            self._theme_btn.setToolTip("Switch to dark theme")

    # ── Startup validation ───────────────────────────────────────────────────

    def _validate_library(self) -> None:
        tracks = library.get_all_tracks()
        orphans = [t for t in tracks if not (TRACKS_DIR / t.folder_name).exists()]
        if not orphans:
            return
        reply = QMessageBox.question(
            self,
            "Missing Files",
            f"{len(orphans)} track(s) have missing folders on disk.\n"
            "Remove their records from the library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for t in orphans:
                library.delete_track(t.id)

    def closeEvent(self, event) -> None:
        self._worker.stop()
        self._worker.wait(2000)
        super().closeEvent(event)
