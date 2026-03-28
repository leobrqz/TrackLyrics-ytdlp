"""
core/settings.py
Key-value settings store backed by app_settings.json in the app root.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from utils.paths import SETTINGS_JSON_PATH

_DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "download_queue_mode": "fifo",
    "download_parallel_workers": 3,
    "lyrics_parallel_with_download": False,
}


def _read_json() -> dict[str, Any]:
    if not SETTINGS_JSON_PATH.exists():
        return dict(_DEFAULTS)
    try:
        with open(SETTINGS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULTS)
    if not isinstance(data, dict):
        return dict(_DEFAULTS)
    merged = dict(_DEFAULTS)
    for k, v in data.items():
        merged[k] = v
    return merged


def _write_json(data: dict[str, Any]) -> None:
    SETTINGS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_JSON_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(SETTINGS_JSON_PATH)


def get_value(key: str, default: Any = None) -> Any:
    data = _read_json()
    if key not in data:
        return default
    return data[key]


def set_value(key: str, value: Any) -> None:
    data = _read_json()
    data[key] = value
    _write_json(data)


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    v = get_value(key, default)
    if v is None:
        return default
    return str(v)


def set_setting(key: str, value: str) -> None:
    set_value(key, value)


def get_download_queue_mode() -> str:
    v = str(get_value("download_queue_mode", "fifo") or "fifo").lower()
    return v if v in ("fifo", "parallel") else "fifo"


def get_download_parallel_workers() -> int:
    try:
        n = int(get_value("download_parallel_workers", 3))
    except (TypeError, ValueError):
        n = 3
    return max(2, min(8, n))


def get_lyrics_parallel_with_download() -> bool:
    v = get_value("lyrics_parallel_with_download", False)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes")
    return bool(v)
