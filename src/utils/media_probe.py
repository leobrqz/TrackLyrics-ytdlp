"""
utils/media_probe.py
Best-effort technical description of on-disk audio files (size, WAV headers, ffprobe).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path


def describe_audio_file(path: Path) -> str:
    if not path.is_file():
        return "File not found"
    size = path.stat().st_size
    size_s = f"{size / (1024 * 1024):.2f} MB ({size:,} bytes)"
    suf = path.suffix.lower()
    if suf == ".wav":
        try:
            with wave.open(str(path), "rb") as w:
                ch = w.getnchannels()
                rate = w.getframerate()
                bits = w.getsampwidth() * 8
                return f"{size_s} · {ch} ch · {rate} Hz · {bits}-bit PCM"
        except Exception:
            return size_s
    if suf == ".mp3":
        ff = shutil.which("ffprobe")
        if ff:
            try:
                proc = subprocess.run(
                    [
                        ff,
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_format",
                        "-show_streams",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=True,
                )
                data = json.loads(proc.stdout)
                fmt = data.get("format") or {}
                br = fmt.get("bit_rate")
                sample_rate = None
                channels = None
                for s in data.get("streams") or []:
                    if s.get("codec_type") == "audio":
                        sample_rate = s.get("sample_rate")
                        channels = s.get("channels")
                        break
                parts: list[str] = [size_s]
                if br:
                    parts.append(f"~{int(int(br) / 1000)} kbps")
                if sample_rate:
                    parts.append(f"{sample_rate} Hz")
                if channels:
                    parts.append(f"{channels} ch")
                return " · ".join(parts)
            except Exception:
                pass
        return f"{size_s} (install ffprobe for bitrate / sample rate)"
    return size_s
