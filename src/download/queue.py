"""
download/queue.py
In-memory FIFO download job queue.
"""
from __future__ import annotations
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

    def add(self, job: DownloadJob) -> None:
        self._jobs.append(job)

    def next_pending(self) -> Optional[DownloadJob]:
        for job in self._jobs:
            if job.status == "pending":
                return job
        return None

    def mark_running(self, job_id: str) -> None:
        self._get(job_id).status = "running"

    def mark_done(self, job_id: str) -> None:
        self._get(job_id).status = "done"

    def mark_failed(self, job_id: str, error: str = "") -> None:
        job = self._get(job_id)
        job.status = "failed"
        job.error = error

    def all_jobs(self) -> list[DownloadJob]:
        return list(self._jobs)

    def pending_count(self) -> int:
        return sum(1 for j in self._jobs if j.status == "pending")

    def _get(self, job_id: str) -> DownloadJob:
        for job in self._jobs:
            if job.job_id == job_id:
                return job
        raise KeyError(f"Job {job_id!r} not found in queue")
