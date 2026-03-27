"""
core/settings.py
Key-value settings store backed by app_settings.json in the app root.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from utils.paths import SETTINGS_JSON_PATH

_DEFAULTS: dict[str, Any] = {"theme": "dark"}


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
    return {**_DEFAULTS, **data}


def _write_json(data: dict[str, Any]) -> None:
    SETTINGS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_JSON_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(SETTINGS_JSON_PATH)


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    data = _read_json()
    val = data.get(key, default)
    if val is None:
        return default
    if isinstance(val, str):
        return val
    return str(val)


def set_setting(key: str, value: str) -> None:
    data = _read_json()
    data[key] = value
    _write_json(data)
