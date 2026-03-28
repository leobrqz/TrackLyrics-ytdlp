"""
download/downloader.py
Thin wrapper around yt-dlp for downloading YouTube media.
Returns structured metadata alongside the downloaded file path.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from utils.logger import get_logger

log = get_logger(__name__)


class DownloadError(Exception):
    pass


def _sanitize_stem_prefix(prefix: str) -> str:
    out = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in prefix)
    return out[:48] if out else ""


def download(
    url: str,
    output_dir: Path,
    format_type: str,
    progress_callback: Optional[Callable[[int], None]] = None,
    file_stem_prefix: Optional[str] = None,
) -> dict:
    """
    Download media from a YouTube URL using yt-dlp.

    Args:
        url: YouTube video URL.
        output_dir: Directory to save the downloaded file.
        format_type: Requested format — 'mp3' or 'wav' (audio-only).
        progress_callback: Optional callable(percent: int) for progress updates.
        file_stem_prefix: Optional prefix for output basename (parallel downloads).

    Returns:
        dict with keys: title, artist, duration, source_url, file_path (Path)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if format_type not in ("mp3", "wav"):
        raise DownloadError(f"Unsupported format: {format_type!r} (use mp3 or wav)")

    safe_prefix = _sanitize_stem_prefix(file_stem_prefix) if file_stem_prefix else ""
    if safe_prefix:
        outtmpl = str(output_dir / f"{safe_prefix}_%(title)s.%(ext)s")
    else:
        outtmpl = str(output_dir / "%(title)s.%(ext)s")

    postprocessors = []
    if format_type == "mp3":
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        })
    elif format_type == "wav":
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        })
    ydl_format = "bestaudio/best"

    _meta: dict = {}

    def _progress_hook(d: dict) -> None:
        if d.get("status") == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                pct = int(downloaded / total * 100)
                progress_callback(pct)
        elif d.get("status") == "finished":
            _meta["_filename"] = d.get("filename", "")

    ydl_opts = {
        "format": ydl_format,
        "outtmpl": outtmpl,
        "postprocessors": postprocessors,
        "progress_hooks": [_progress_hook],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(str(exc)) from exc

    if info is None:
        raise DownloadError(f"yt-dlp returned no info for URL: {url}")

    # Resolve the actual downloaded file
    file_path = _resolve_file(output_dir, info, format_type, stem_prefix=safe_prefix or None)

    title = info.get("title") or info.get("fulltitle") or "Unknown Title"
    artist = (
        info.get("artist")
        or info.get("uploader")
        or info.get("channel")
        or "Unknown Artist"
    )
    duration = int(info.get("duration") or 0)

    log.info("Downloaded: %s — %s  [%s]", artist, title, format_type)

    return {
        "title": title,
        "artist": artist,
        "duration": duration,
        "source_url": url,
        "file_path": file_path,
    }


def _resolve_file(
    output_dir: Path,
    info: dict,
    format_type: str,
    stem_prefix: Optional[str] = None,
) -> Path:
    """Find the actual output file after yt-dlp (postprocessors may change extension)."""
    # yt-dlp stores the final filename in info["requested_downloads"] when available
    rds = info.get("requested_downloads")
    if rds:
        candidate = Path(rds[0].get("filepath", ""))
        if candidate.exists():
            return candidate

    # Fallback: scan output_dir for the newest file matching the expected extension
    ext = format_type  # 'mp3' | 'wav'
    pattern = f"{stem_prefix}_*.{ext}" if stem_prefix else f"*.{ext}"
    candidates = sorted(output_dir.glob(pattern), key=os.path.getmtime, reverse=True)
    if candidates:
        return candidates[0]

    raise DownloadError(
        f"Could not locate downloaded file in {output_dir} for format '{format_type}'"
    )
