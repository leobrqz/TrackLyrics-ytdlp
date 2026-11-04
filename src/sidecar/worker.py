"""Qt-free download pipeline for the Tauri sidecar."""
from __future__ import annotations

import concurrent.futures
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import core.library as library
from core.database import get_connection
from core.settings import (
    get_download_parallel_workers,
    get_download_queue_mode,
    get_lyrics_parallel_with_download,
)
from download.downloader import DownloadError, download
from download.queue import DownloadJob, DownloadQueue
from download.url_expand import expand_youtube_inputs
from lyrics.scraper import scrape_lyrics_sync
from utils.logger import get_logger, log_structured
from utils.paths import TEMP_DIR, TRACKS_DIR
from utils.sanitize import build_track_name

log = get_logger(__name__)
EventCallback = Callable[[str, dict[str, Any]], None]


class SidecarDownloadWorker:
    """Owns the in-memory queue and emits per-job events without Qt signals."""

    def __init__(self, emit: EventCallback) -> None:
        self._emit = emit
        self._queue = DownloadQueue()
        self._records: dict[str, dict[str, Any]] = {}
        self._records_lock = threading.RLock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="TrackLyricsDownloadWorker",
            daemon=True,
        )
        self._thread.start()

    def enqueue(self, url: str, format_type: str) -> dict[str, Any]:
        result = self.enqueue_inputs([url], format_type)
        if result["failedInputs"] or not result["jobs"]:
            raise ValueError(result["failedInputs"][0]["message"] if result["failedInputs"] else "The URL did not produce a download job.")
        return result["jobs"][0]

    def enqueue_inputs(self, urls: list[str], format_type: str) -> dict[str, Any]:
        if format_type not in {"mp3", "wav"}:
            raise ValueError("formatType must be 'mp3' or 'wav'.")
        normalized = [line.strip() for line in urls if isinstance(line, str) and line.strip()]
        if not normalized:
            raise ValueError("Add at least one YouTube URL.")
        if len(normalized) > 50:
            raise ValueError("Add no more than 50 URL lines at a time.")

        expanded, failed = expand_youtube_inputs(normalized)
        created: list[DownloadJob] = []
        now = time.time()
        with self._records_lock:
            for url in expanded:
                job = DownloadJob(url=url, format_type=format_type)
                created.append(job)
                self._records[job.job_id] = {
                    "jobId": job.job_id,
                    "url": job.url,
                    "formatType": job.format_type,
                    "status": "pending",
                    "stage": "Queued",
                    "progress": 0,
                    "error": None,
                    "createdAt": now,
                }
        for job in created:
            self._emit_status(job, "pending", "Queued")
        self._queue.add_many(created)
        self._wake.set()
        jobs = [self._record(job.job_id) for job in created]
        return {
            "jobs": jobs,
            "failedInputs": [{"url": url, "message": error} for url, error in failed],
        }

    def snapshot(self) -> list[dict[str, Any]]:
        with self._records_lock:
            records = list(self._records.values())
            result = []
            for record in sorted(records, key=lambda item: item["createdAt"]):
                item = dict(record)
                item["createdAt"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record["createdAt"])
                )
                result.append(item)
            return result

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        log.info("Sidecar download worker started")
        while not self._stop.is_set():
            if get_download_queue_mode() == "fifo":
                job = self._queue.take_next_pending()
                if job is None:
                    self._wait()
                    continue
                self._pipeline_fifo(job)
            else:
                count = get_download_parallel_workers()
                jobs = self._queue.take_up_to_n_pending(count)
                if not jobs:
                    self._wait()
                    continue
                self._pipeline_parallel(jobs, count)
        log.info("Sidecar download worker stopped")

    def _wait(self) -> None:
        self._wake.wait(0.4)
        self._wake.clear()

    def _pipeline_fifo(self, job: DownloadJob) -> None:
        try:
            self._set_status(job, "running", "Downloading")
            meta = self._download(job)
        except Exception as exc:
            self._fail(job, "Download", str(exc), "Check the URL and your connection.")
            return
        try:
            context = self._save_to_library(job, meta)
        except Exception as exc:
            self._fail(job, "Storage", str(exc), "Check library folder permissions and free disk space.")
            return
        if context is None:
            return
        try:
            result = self._scrape(context)
            self._apply_lyrics(context, result)
            self._finish(job, context["trackId"])
        except Exception as exc:
            self._fail(job, "Lyrics", str(exc), "The track is saved; lyrics can be checked again later.")

    def _pipeline_parallel(self, jobs: list[DownloadJob], max_workers: int) -> None:
        for job in jobs:
            self._set_status(job, "running", "Downloading")
        workers = min(max_workers, len(jobs))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {job.job_id: pool.submit(self._download, job) for job in jobs}
            downloaded: list[tuple[DownloadJob, dict[str, Any]]] = []
            for job in jobs:
                try:
                    downloaded.append((job, futures[job.job_id].result()))
                except Exception as exc:
                    self._fail(job, "Download", str(exc), "Check the URL and your connection.")

        contexts: list[tuple[DownloadJob, dict[str, Any]]] = []
        for job, meta in downloaded:
            try:
                context = self._save_to_library(job, meta)
                if context is not None:
                    contexts.append((job, context))
            except Exception as exc:
                self._fail(job, "Storage", str(exc), "Check library folder permissions and free disk space.")

        if not contexts:
            return

        if get_lyrics_parallel_with_download() and len(contexts) > 1:
            lyric_workers = min(get_download_parallel_workers(), len(contexts))
            with concurrent.futures.ThreadPoolExecutor(max_workers=lyric_workers) as pool:
                futures = {
                    job.job_id: pool.submit(self._scrape, context)
                    for job, context in contexts
                }
                for job, context in contexts:
                    try:
                        result = futures[job.job_id].result()
                        self._apply_lyrics(context, result)
                        self._finish(job, context["trackId"])
                    except Exception as exc:
                        self._fail(job, "Lyrics", str(exc), "The track is saved; lyrics can be checked again later.")
        else:
            for job, context in contexts:
                try:
                    result = self._scrape(context)
                    self._apply_lyrics(context, result)
                    self._finish(job, context["trackId"])
                except Exception as exc:
                    self._fail(job, "Lyrics", str(exc), "The track is saved; lyrics can be checked again later.")

    def _download(self, job: DownloadJob) -> dict[str, Any]:
        prefix = job.job_id.replace("-", "")
        return download(
            url=job.url,
            output_dir=TEMP_DIR,
            format_type=job.format_type,
            progress_callback=lambda percent: self._set_progress(job, percent),
            file_stem_prefix=prefix,
        )

    def _save_to_library(self, job: DownloadJob, meta: dict[str, Any]) -> Optional[dict[str, Any]]:
        title = str(meta.get("title") or "Unknown Title")
        artist = str(meta.get("artist") or "Unknown Artist")
        duration = int(meta.get("duration") or 0)
        source_url = str(meta.get("source_url") or job.url)
        downloaded_file = Path(meta["file_path"])

        if library.track_exists(artist, title):
            self._emit("downloads.duplicate", {"jobId": job.job_id, "artist": artist, "title": title})

        self._set_status(job, "running", "Saving to library")
        track_id = library.insert_track(
            title=title,
            artist=artist,
            duration=duration,
            folder_name=f"__tmp_{job.job_id}",
            source_url=source_url,
            media_files=[],
        )

        folder_name = build_track_name(artist, title, track_id)
        track_folder = TRACKS_DIR / folder_name
        track_folder.mkdir(parents=True, exist_ok=True)
        conn = get_connection()
        try:
            with conn:
                conn.execute("UPDATE tracks SET folder_name = ? WHERE id = ?", (folder_name, track_id))
        finally:
            conn.close()

        destination = track_folder / f"{folder_name}.{job.format_type}"
        shutil.move(str(downloaded_file), str(destination))
        library.add_media_file(
            track_id=track_id,
            file_name=destination.name,
            format_type=job.format_type,
            has_audio=job.format_type in {"mp3", "wav"},
        )
        library.update_lyrics(
            track_id=track_id,
            original_path=None,
            ptbr_path=None,
            original_url=None,
            ptbr_url=None,
            has_original=False,
            has_ptbr=False,
            search_status="pending",
        )
        self._emit("library.track_saved", {"trackId": track_id})
        self._set_status(job, "running", "Searching lyrics")
        return {
            "trackId": track_id,
            "title": title,
            "artist": artist,
            "folderName": folder_name,
            "trackFolder": track_folder,
        }

    def _scrape(self, context: dict[str, Any]) -> dict[str, Any]:
        try:
            return scrape_lyrics_sync(context["title"], context["artist"])
        except Exception as exc:
            log.exception("Lyrics lookup raised for track %s", context["trackId"])
            return {"has_original": False, "has_ptbr": False, "failure_reason": str(exc)}

    def _apply_lyrics(self, context: dict[str, Any], result: dict[str, Any]) -> None:
        track_folder: Path = context["trackFolder"]
        lyrics_dir = track_folder / "lyrics"
        lyrics_dir.mkdir(exist_ok=True)

        original_path: Optional[str] = None
        ptbr_path: Optional[str] = None
        if result.get("has_original") and result.get("original_text"):
            path = lyrics_dir / "lyrics_original.md"
            path.write_text(str(result["original_text"]), encoding="utf-8")
            original_path = str(path.relative_to(track_folder))
        if result.get("has_ptbr") and result.get("ptbr_text"):
            path = lyrics_dir / "lyrics_ptbr.md"
            path.write_text(str(result["ptbr_text"]), encoding="utf-8")
            ptbr_path = str(path.relative_to(track_folder))

        failure = result.get("failure_reason")
        no_match = failure in {"discover_no_candidates", "all_candidates_filtered"}
        search_status = "failed" if failure and not no_match else "complete"
        library.update_lyrics(
            track_id=context["trackId"],
            original_path=original_path,
            ptbr_path=ptbr_path,
            original_url=result.get("original_url"),
            ptbr_url=result.get("ptbr_url"),
            has_original=bool(result.get("has_original")),
            has_ptbr=bool(result.get("has_ptbr")),
            search_status=search_status,
        )
        if failure and not no_match:
            self._emit(
                "app.error",
                {
                    "operation": "Lyrics search",
                    "message": str(failure),
                    "hint": "The track was saved. Lyrics can be checked again later.",
                    "trackId": context["trackId"],
                },
            )
        self._emit("lyrics.ready", {"trackId": context["trackId"]})

    def _set_progress(self, job: DownloadJob, percent: int) -> None:
        value = max(0, min(100, int(percent)))
        with self._records_lock:
            record = self._records.get(job.job_id)
            if record is None:
                return
            record["progress"] = value
        self._emit("downloads.progress", {"jobId": job.job_id, "progress": value})

    def _set_status(self, job: DownloadJob, status: str, stage: str) -> None:
        with self._records_lock:
            record = self._records.get(job.job_id)
            if record is None:
                return
            record["status"] = status
            record["stage"] = stage
        self._emit_status(job, status, stage)

    def _emit_status(self, job: DownloadJob, status: str, stage: str, error: Optional[str] = None) -> None:
        payload: dict[str, Any] = {
            "jobId": job.job_id,
            "status": status,
            "stage": stage,
        }
        if error:
            payload["error"] = error
        self._emit("downloads.status", payload)

    def _finish(self, job: DownloadJob, track_id: int) -> None:
        self._queue.mark_done(job.job_id)
        with self._records_lock:
            record = self._records[job.job_id]
            record["status"] = "done"
            record["stage"] = "Complete"
            record["progress"] = 100
            record["trackId"] = track_id
        self._emit_status(job, "done", "Complete")
        self._emit("downloads.progress", {"jobId": job.job_id, "progress": 100})
        log.info("Download job %s completed for track %s", job.job_id, track_id)

    def _fail(self, job: DownloadJob, operation: str, message: str, hint: str) -> None:
        try:
            self._queue.mark_failed(job.job_id, message)
        except KeyError:
            pass
        with self._records_lock:
            record = self._records.get(job.job_id)
            if record is not None:
                record["status"] = "failed"
                record["stage"] = operation
                record["error"] = message
        self._emit_status(job, "failed", operation, error=message)
        self._emit(
            "app.error",
            {"operation": operation, "message": message, "hint": hint, "jobId": job.job_id},
        )
        log_structured("job_failed", job_id=job.job_id, operation=operation, reason=message)
        log.error("[%s] %s — %s", operation, message, hint)

    def _record(self, job_id: str) -> dict[str, Any]:
        with self._records_lock:
            record = self._records[job_id]
            item = dict(record)
            item["createdAt"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record["createdAt"])
            )
            return item
