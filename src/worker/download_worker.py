"""
worker/download_worker.py
QThread worker that owns the download queue processing loop.

Pipeline per job:
  1. Download media via yt-dlp
  2. Detect duplicates (warn only, never block)
  3. Move file into tracks/<folder_name>/
  4. Insert track + media_files + blank lyrics row into DB
  5. Emit track_saved → UI refreshes library
  6. Scrape lyrics (non-blocking on failure)
  7. Save lyrics .md files to disk
  8. Update lyrics row in DB (includes letras URLs when successful)
  9. Emit lyrics_ready → UI refreshes lyrics panel
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

import core.library as library
from download.downloader import download, DownloadError
from download.queue import DownloadJob, DownloadQueue
from lyrics.scraper import scrape_lyrics_sync
from utils.logger import get_logger, log_structured
from utils.paths import TRACKS_DIR, TEMP_DIR
from utils.sanitize import build_track_name

log = get_logger(__name__)

AUDIO_FORMATS = {"mp3", "wav"}


class DownloadWorker(QThread):
    # ---- Signals emitted to the UI ----------------------------------------
    progress_updated  = Signal(str, int)      # job_id, percent 0-100
    status_changed    = Signal(str, str)      # job_id, human-readable status
    track_saved       = Signal(int)           # track_id
    lyrics_ready      = Signal(int)           # track_id
    duplicate_detected = Signal(str, str)     # artist, title
    error_occurred    = Signal(str, str, str) # operation, reason, hint

    def __init__(self, queue: DownloadQueue, parent=None) -> None:
        super().__init__(parent)
        self._queue = queue
        self._running = True

    # ---- Thread entry point ------------------------------------------------

    def run(self) -> None:
        log.info("DownloadWorker started")
        while self._running:
            job = self._queue.next_pending()
            if job is None:
                self.msleep(500)  # poll every 500 ms
                continue
            self._process_job(job)

    def stop(self) -> None:
        self._running = False

    # ---- Job pipeline -------------------------------------------------------

    def _process_job(self, job: DownloadJob) -> None:
        self._queue.mark_running(job.job_id)
        self._emit_status(job, "Downloading…")
        log.info("Processing job %s  url=%s  fmt=%s", job.job_id, job.url, job.format_type)

        # ── Step 1: Download ─────────────────────────────────────────────────
        try:
            meta = download(
                url=job.url,
                output_dir=TEMP_DIR,
                format_type=job.format_type,
                progress_callback=lambda pct: self.progress_updated.emit(job.job_id, pct),
            )
        except DownloadError as exc:
            self._fail(job, "Download Error", str(exc), "Check the URL and your internet connection.")
            return

        title: str = meta["title"]
        artist: str = meta["artist"]
        duration: int = meta["duration"]
        # YouTube URL used for this download (same as user-submitted job URL)
        source_url: str = meta.get("source_url") or job.url
        downloaded_file: Path = meta["file_path"]

        # ── Step 2: Duplicate detection (warn only) ──────────────────────────
        if library.track_exists(artist, title):
            log.warning("Duplicate detected: %s — %s", artist, title)
            self.duplicate_detected.emit(artist, title)

        # ── Step 3: Reserve a track_id to build folder name ──────────────────
        # Insert the track first (with dummy folder_name), then rename
        self._emit_status(job, "Saving to library…")
        try:
            placeholder = f"__tmp_{job.job_id}"
            track_id = library.insert_track(
                title=title,
                artist=artist,
                duration=duration,
                folder_name=placeholder,
                source_url=source_url,
                media_files=[],   # filled in after folder is ready
            )
        except Exception as exc:
            self._fail(job, "Storage Error", str(exc), "Check disk space and permissions.")
            return

        folder_name = build_track_name(artist, title, track_id)
        track_folder = TRACKS_DIR / folder_name
        track_folder.mkdir(parents=True, exist_ok=True)

        # Update folder_name in DB now that we have the real ID
        try:
            from core.database import get_connection
            conn = get_connection()
            with conn:
                conn.execute(
                    "UPDATE tracks SET folder_name = ? WHERE id = ?",
                    (folder_name, track_id),
                )
            conn.close()
        except Exception as exc:
            self._fail(job, "Storage Error", str(exc), "Could not update track folder name.")
            return

        # ── Step 4: Move downloaded file into track folder ───────────────────
        dest_file = track_folder / f"{folder_name}.{job.format_type}"
        try:
            shutil.move(str(downloaded_file), str(dest_file))
        except OSError as exc:
            self._fail(job, "Storage Error", str(exc), "Could not move file to library folder.")
            return

        has_audio = job.format_type in AUDIO_FORMATS

        # ── Step 5: Register primary media file in DB ────────────────────────
        try:
            library.add_media_file(
                track_id=track_id,
                file_name=dest_file.name,
                format_type=job.format_type,
                has_audio=has_audio,
            )
        except Exception as exc:
            self._fail(job, "Storage Error", str(exc), "Could not register media file in library.")
            return

        # ── Step 6: Emit track_saved so UI can refresh immediately ───────────
        self.track_saved.emit(track_id)
        self._emit_status(job, "Scraping lyrics…")

        # ── Step 7: Scrape lyrics ────────────────────────────────────────────
        lyrics_dir = track_folder / "lyrics"
        lyrics_dir.mkdir(exist_ok=True)

        scrape_result = self._safe_scrape(title, artist)
        original_path: Optional[str] = None
        ptbr_path: Optional[str] = None

        if scrape_result.get("has_original") and scrape_result.get("original_text"):
            orig_file = lyrics_dir / "lyrics_original.md"
            orig_file.write_text(scrape_result["original_text"], encoding="utf-8")
            original_path = str(orig_file.relative_to(track_folder))

        if scrape_result.get("has_ptbr") and scrape_result.get("ptbr_text"):
            ptbr_file = lyrics_dir / "lyrics_ptbr.md"
            ptbr_file.write_text(scrape_result["ptbr_text"], encoding="utf-8")
            ptbr_path = str(ptbr_file.relative_to(track_folder))

        # ── Step 8: Persist lyrics metadata ─────────────────────────────────
        try:
            library.update_lyrics(
                track_id=track_id,
                original_path=original_path,
                ptbr_path=ptbr_path,
                original_url=scrape_result.get("original_url"),
                ptbr_url=scrape_result.get("ptbr_url"),
                has_original=bool(scrape_result.get("has_original")),
                has_ptbr=bool(scrape_result.get("has_ptbr")),
            )
        except Exception as exc:
            log.warning("Could not update lyrics metadata for track %d: %s", track_id, exc)

        self.lyrics_ready.emit(track_id)

        # ── Step 9: Done ─────────────────────────────────────────────────────
        self._queue.mark_done(job.job_id)
        self._emit_status(job, "Done")
        log.info("Job %s complete. track_id=%d", job.job_id, track_id)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _safe_scrape(self, title: str, artist: str) -> dict:
        """Run scraper and absorb any exception — lyrics are always non-fatal."""
        try:
            result = scrape_lyrics_sync(title, artist)
            if result.get("failure_reason"):
                log.warning(
                    "Lyrics scrape warning for '%s' — %s",
                    title, result["failure_reason"],
                )
                self.error_occurred.emit(
                    "Lyrics Search",
                    result["failure_reason"],
                    "The track was saved without lyrics.",
                )
            return result
        except Exception as exc:
            log.warning("Scraper raised unexpectedly: %s", exc)
            self.error_occurred.emit(
                "Lyrics Error",
                str(exc),
                "The track was saved without lyrics. You can retry later.",
            )
            return {"has_original": False, "has_ptbr": False}

    def _emit_status(self, job: DownloadJob, msg: str) -> None:
        self.status_changed.emit(job.job_id, msg)

    def _fail(self, job: DownloadJob, operation: str, reason: str, hint: str) -> None:
        log.error("[%s] %s — %s", operation, reason, hint)
        log_structured("job_failed", job_id=job.job_id, operation=operation, reason=reason)
        self._queue.mark_failed(job.job_id, reason)
        self.status_changed.emit(job.job_id, f"Failed: {operation}")
        self.error_occurred.emit(operation, reason, hint)
