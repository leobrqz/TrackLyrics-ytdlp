"""
download/url_expand.py
Resolve YouTube playlist (and channel tab) URLs into per-video watch URLs for the job queue.
Single-video URLs pass through as one entry.
"""
from __future__ import annotations

import re
from typing import Optional

import yt_dlp

from download.downloader import DownloadError

_YT_VIDEO_ID = re.compile(r"^[0-9A-Za-z_-]{11}$")


def _watch_url_from_entry(entry: object) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    vid = entry.get("id")
    if isinstance(vid, str) and _YT_VIDEO_ID.fullmatch(vid):
        return f"https://www.youtube.com/watch?v={vid}"
    for key in ("url", "webpage_url", "original_url"):
        u = entry.get(key)
        if isinstance(u, str) and u.startswith("http") and ("youtu.be" in u or "youtube.com" in u):
            return u
    return None


def expand_youtube_url(url: str) -> list[str]:
    """
    If url is a playlist (or multi-entry page), return one canonical watch URL per video.
    If it is a single video, return a list of one URL.
    """
    url = (url or "").strip()
    if not url:
        return []

    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "noplaylist": False,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(str(exc)) from exc

    if not info:
        raise DownloadError("No information returned for URL")

    entries = info.get("entries")
    if entries is not None:
        out: list[str] = []
        for e in entries:
            w = _watch_url_from_entry(e)
            if w:
                out.append(w)
        if not out:
            raise DownloadError("No videos found (empty, private, or unavailable playlist)")
        return out

    for key in ("webpage_url", "original_url", "url"):
        w = info.get(key)
        if isinstance(w, str) and w.startswith("http"):
            return [w]

    return [url]


def expand_youtube_inputs(urls: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Expand each user line (video or playlist) into watch URLs.
    Returns (expanded_urls_in_order, [(input_line, error_message), ...]).
    """
    expanded: list[str] = []
    failed: list[tuple[str, str]] = []
    for raw in urls:
        line = raw.strip()
        if not line:
            continue
        try:
            expanded.extend(expand_youtube_url(line))
        except DownloadError as exc:
            failed.append((line, str(exc)))
    return expanded, failed
