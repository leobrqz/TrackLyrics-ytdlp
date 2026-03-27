"""
download/converter.py
Thin wrapper around FFmpeg for converting media to alternate formats.
The original file is preserved; a new file is produced.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)


class ConversionError(Exception):
    pass


def convert(input_path: Path, target_format: str, output_path: Path) -> Path:
    """
    Convert a media file to the target format using FFmpeg.

    Args:
        input_path:    Source file path.
        target_format: Target format extension ('mp3', 'wav').
        output_path:   Destination file path (including extension).

    Returns:
        The output_path on success.

    Raises:
        ConversionError on FFmpeg failure.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",                    # overwrite without asking
        "-i", str(input_path),
    ]

    if target_format == "mp3":
        cmd += ["-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k"]
    elif target_format == "wav":
        cmd += ["-vn", "-ar", "44100", "-ac", "2"]
    else:
        raise ConversionError(f"Unsupported target format: {target_format!r}")

    cmd.append(str(output_path))

    log.info("Converting %s → %s", input_path.name, output_path.name)

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise ConversionError(
            f"FFmpeg failed (exit {result.returncode}): {stderr[-500:]}"
        )

    log.info("Conversion complete: %s", output_path.name)
    return output_path
