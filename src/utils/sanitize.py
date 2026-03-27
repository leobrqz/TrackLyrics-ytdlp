"""
utils/sanitize.py
Filename and folder name sanitization utilities.
"""
import re


# Characters illegal on Windows, Linux, and macOS
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_SPACE = re.compile(r' {2,}')


def sanitize_filename(s: str) -> str:
    """Remove illegal characters, collapse spaces, strip edge dots/spaces."""
    s = _ILLEGAL.sub('', s)
    s = _MULTI_SPACE.sub(' ', s)
    s = s.strip('. ')
    return s or 'Unknown'


def build_track_name(artist: str, title: str, track_id: int) -> str:
    """
    Build the canonical folder/file base name for a track.
    Format: '<artist> - <title> - <id>'
    """
    safe_artist = sanitize_filename(artist) if artist else 'Unknown Artist'
    safe_title = sanitize_filename(title) if title else 'Unknown Title'
    return f"{safe_artist} - {safe_title} - {track_id}"
