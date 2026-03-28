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

import concurrent.futures
import shutil
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

import core.library as library
from core.settings import (
    get_download_parallel_workers,
    get_download_queue_mode,
    get_lyrics_parallel_with_download,
)
from download.downloader import download, DownloadError
from download.queue import DownloadJob, DownloadQueue
from lyrics.scraper import scrape_lyrics_sync
from utils.logger import get_logger, log_structured
from utils.paths import TRACKS_DIR, TEMP_DIR
from utils.sanitize import build_track_name

log = get_logger(__name__)

AUDIO_FORMATS = {"mp3", "wav"}


class DownloadWorker(QThread):
    progress_updated = Signal(str, int)
    status_changed = Signal(str, str)
    track_saved = Signal(int)
    lyrics_ready = Signal(int)
    duplicate_detected = Signal(str, str)
    error_occurred = Signal(str, str, str)

    def __init__(self, queue: DownloadQueue, parent=None) -> None:
        super().__init__(parent)
        self._queue = queue
        self._running = True

    def run(self) -> None:
        log.info("DownloadWorker started")
        while self._running:
            if get_download_queue_mode() == "fifo":
                job = self._queue.take_next_pending()
                if job is None:
                    self.msleep(500)
                    continue
                self._pipeline_fifo_job(job)
            else:
                n = get_download_parallel_workers()
                jobs = self._queue.take_up_to_n_pending(n)
                if not jobs:
                    self.msleep(500)
                    continue
                self._pipeline_parallel_batch(jobs, n)

    def stop(self) -> None:
        self._running = False

    # ── FIFO: one job end-to-end ────────────────────────────────────────────

    def _pipeline_fifo_job(self, job: DownloadJob) -> None:
        try:
            meta = self._download_job_media(job)
        except DownloadError as exc:
            self._fail(
                job,
                "Download Error",
                str(exc),
                "Check the URL and your internet connection.",
            )
            return
        ctx = self._library_phase(job, meta)
        if ctx is None:
            return
        self._emit_status(job, "Scraping lyrics…")
        scrape_result = self._safe_scrape(ctx["title"], ctx["artist"])
        self._apply_lyrics_files_and_db(job, ctx, scrape_result)
        self._finish_job_success(job, ctx["track_id"])

    # ── Parallel: N downloads, then library (serial), then lyrics ───────────

    def _pipeline_parallel_batch(self, jobs: list[DownloadJob], max_workers: int) -> None:
        workers = min(max_workers, len(jobs))
        for j in jobs:
            self._emit_status(j, "Downloading…")

        metas: list[tuple[DownloadJob, Optional[dict]]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(self._download_job_media, job) for job in jobs]
            for job, fut in zip(jobs, futs):
                try:
                    metas.append((job, fut.result()))
                except DownloadError as exc:
                    self._fail(
                        job,
                        "Download Error",
                        str(exc),
                        "Check the URL and your internet connection.",
                    )
                    metas.append((job, None))
                except Exception as exc:
                    self._fail(
                        job,
                        "Download Error",
                        str(exc),
                        "Check the URL and your internet connection.",
                    )
                    metas.append((job, None))

        contexts: list[tuple[DownloadJob, dict[str, Any]]] = []
        for job, meta in metas:
            if meta is None:
                continue
            ctx = self._library_phase(job, meta)
            if ctx is not None:
                contexts.append((job, ctx))

        if not contexts:
            return

        lyrics_parallel = (
            get_lyrics_parallel_with_download() and len(contexts) > 1
        )
        if lyrics_parallel:
            n_ly = min(get_download_parallel_workers(), len(contexts))
            for job, _ctx in contexts:
                self._emit_status(job, "Scraping lyrics…")
            with concurrent.futures.ThreadPoolExecutor(max_workers=n_ly) as ex:
                futs = [
                    (
                        job,
                        ctx,
                        ex.submit(scrape_lyrics_sync, ctx["title"], ctx["artist"]),
                    )
                    for job, ctx in contexts
                ]
                for job, ctx, fut in futs:
                    try:
                        raw = fut.result()
                    except Exception as exc:
                        log.warning("Lyrics pool scrape raised: %s", exc)
                        self.error_occurred.emit(
                            "Lyrics Error",
                            str(exc),
                            "The track was saved without lyrics.",
                        )
                        raw = {"has_original": False, "has_ptbr": False}
                    scrape_result = self._post_process_scrape_result(
                        raw, ctx["title"]
                    )
                    self._apply_lyrics_files_and_db(job, ctx, scrape_result)
                    self._finish_job_success(job, ctx["track_id"])
        else:
            for job, ctx in contexts:
                self._emit_status(job, "Scraping lyrics…")
                scrape_result = self._safe_scrape(ctx["title"], ctx["artist"])
                self._apply_lyrics_files_and_db(job, ctx, scrape_result)
                self._finish_job_success(job, ctx["track_id"])

    def _download_job_media(self, job: DownloadJob) -> dict:
        prefix = job.job_id.replace("-", "")
        return download(
            url=job.url,
            output_dir=TEMP_DIR,
            format_type=job.format_type,
            progress_callback=lambda pct: self.progress_updated.emit(job.job_id, pct),
            file_stem_prefix=prefix,
        )

    def _library_phase(
        self, job: DownloadJob, meta: dict
    ) -> Optional[dict[str, Any]]:
        title: str = meta["title"]
        artist: str = meta["artist"]
        duration: int = meta["duration"]
        source_url: str = meta.get("source_url") or job.url
        downloaded_file: Path = meta["file_path"]

        if library.track_exists(artist, title):
            log.warning("Duplicate detected: %s — %s", artist, title)
            self.duplicate_detected.emit(artist, title)

        self._emit_status(job, "Saving to library…")
        try:
            placeholder = f"__tmp_{job.job_id}"
            track_id = library.insert_track(
                title=title,
                artist=artist,
                duration=duration,
                folder_name=placeholder,
                source_url=source_url,
                media_files=[],
            )
        except Exception as exc:
            self._fail(job, "Storage Error", str(exc), "Check disk space and permissions.")
            return None

        folder_name = build_track_name(artist, title, track_id)
        track_folder = TRACKS_DIR / folder_name
        track_folder.mkdir(parents=True, exist_ok=True)

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
            return None

        dest_file = track_folder / f"{folder_name}.{job.format_type}"
        try:
            shutil.move(str(downloaded_file), str(dest_file))
        except OSError as exc:
            self._fail(job, "Storage Error", str(exc), "Could not move file to library folder.")
            return None

        has_audio = job.format_type in AUDIO_FORMATS
        try:
            library.add_media_file(
                track_id=track_id,
                file_name=dest_file.name,
                format_type=job.format_type,
                has_audio=has_audio,
            )
        except Exception as exc:
            self._fail(job, "Storage Error", str(exc), "Could not register media file in library.")
            return None

        self.track_saved.emit(track_id)
        return {
            "track_id": track_id,
            "title": title,
            "artist": artist,
            "track_folder": track_folder,
            "folder_name": folder_name,
        }

    def _apply_lyrics_files_and_db(
        self,
        job: DownloadJob,
        ctx: dict[str, Any],
        scrape_result: dict,
    ) -> None:
        track_id: int = ctx["track_id"]
        track_folder: Path = ctx["track_folder"]
        lyrics_dir = track_folder / "lyrics"
        lyrics_dir.mkdir(exist_ok=True)

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

    def _finish_job_success(self, job: DownloadJob, track_id: int) -> None:
        self._queue.mark_done(job.job_id)
        self._emit_status(job, "Done")
        log.info("Job %s complete. track_id=%d", job.job_id, track_id)

    def _post_process_scrape_result(self, result: dict, title: str) -> dict:
        if result.get("failure_reason"):
            log.warning(
                "Lyrics scrape warning for '%s' — %s",
                title,
                result["failure_reason"],
            )
            self.error_occurred.emit(
                "Lyrics Search",
                result["failure_reason"],
                "The track was saved without lyrics.",
            )
        return result

    def _safe_scrape(self, title: str, artist: str) -> dict:
        try:
            result = scrape_lyrics_sync(title, artist)
            return self._post_process_scrape_result(result, title)
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
