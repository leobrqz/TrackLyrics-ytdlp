"""
download/queue.py
In-memory FIFO download job queue.
"""
from __future__ import annotations
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DownloadJob:
    url: str
    format_type: str              # 'mp3' | 'wav'
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"       # 'pending' | 'running' | 'done' | 'failed'
    error: Optional[str] = None   # error message if failed


class DownloadQueue:
    def __init__(self) -> None:
        self._jobs: list[DownloadJob] = []
        self._lock = threading.Lock()

    def add(self, job: DownloadJob) -> None:
        with self._lock:
            self._jobs.append(job)

    def take_next_pending(self) -> Optional[DownloadJob]:
        with self._lock:
            for job in self._jobs:
                if job.status == "pending":
                    job.status = "running"
                    return job
            return None

    def take_up_to_n_pending(self, n: int) -> list[DownloadJob]:
        if n < 1:
            return []
        with self._lock:
            out: list[DownloadJob] = []
            for job in self._jobs:
                if job.status == "pending" and len(out) < n:
                    job.status = "running"
                    out.append(job)
            return out

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            self._get_unlocked(job_id).status = "running"

    def mark_done(self, job_id: str) -> None:
        with self._lock:
            self._get_unlocked(job_id).status = "done"

    def mark_failed(self, job_id: str, error: str = "") -> None:
        with self._lock:
            job = self._get_unlocked(job_id)
            job.status = "failed"
            job.error = error

    def all_jobs(self) -> list[DownloadJob]:
        with self._lock:
            return list(self._jobs)

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs if j.status == "pending")

    def _get_unlocked(self, job_id: str) -> DownloadJob:
        for job in self._jobs:
            if job.job_id == job_id:
                return job
        raise KeyError(f"Job {job_id!r} not found in queue")
