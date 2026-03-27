"""
utils/logger.py
Structured logger for the application.
Writes human-readable lines to the console and a rolling log file.
Structured (machine-readable) events are written as JSON lines.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from utils.paths import LOGS_DIR

_LOG_FILE = LOGS_DIR / "app.log"

# Configure the root handler once
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


def log_structured(operation: str, **kwargs) -> None:
    """
    Write a JSON-serialisable structured event to the log file.
    This is used for machine-readable audit entries (scrape events, errors, etc.).
    """
    entry = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "operation": operation,
        **kwargs,
    }
    with open(_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
