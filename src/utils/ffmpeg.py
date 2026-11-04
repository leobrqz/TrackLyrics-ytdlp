"""Resolve FFmpeg from the system first, then from the bundled wheel."""
from __future__ import annotations

import shutil
from pathlib import Path


def get_ffmpeg_executable() -> Path:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        candidate = Path(system_ffmpeg).resolve()
        if candidate.is_file():
            return candidate

    try:
        import imageio_ffmpeg

        bundled_ffmpeg = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    except (ImportError, RuntimeError, OSError) as exc:
        raise FileNotFoundError(
            "FFmpeg was not found on PATH and the bundled FFmpeg binary is unavailable."
        ) from exc

    if not bundled_ffmpeg.is_file():
        raise FileNotFoundError("The bundled FFmpeg executable does not exist.")
    return bundled_ffmpeg
