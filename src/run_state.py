"""Run state persistence - tracks last successful send to compute fetch window.

状态文件是辅助路径：读写失败只 log 不抛，缺失/损坏时回退到默认窗口。
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = "/app/data/last_success.json"
MIN_WINDOW_HOURS = 1
MAX_WINDOW_HOURS = 48
FALLBACK_WINDOW_HOURS = 24


def _state_file_path() -> str:
    return os.environ.get("STATE_FILE", DEFAULT_STATE_FILE)


def load_last_success() -> datetime | None:
    """Read the last successful send time; None if missing or unreadable."""
    path = _state_file_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        last = datetime.fromisoformat(data["last_success"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return last
    except FileNotFoundError:
        logger.info("No state file at %s (first run?)", path)
        return None
    except Exception as exc:
        logger.warning("Failed to read state file %s: %s: %s", path, type(exc).__name__, exc)
        return None


def save_last_success(now: datetime) -> None:
    """Persist the successful send time; failures are logged, never raised."""
    path = _state_file_path()
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"last_success": now.isoformat()}, f)
        logger.info("Saved last success time %s to %s", now.isoformat(), path)
    except Exception as exc:
        logger.warning("Failed to write state file %s: %s: %s", path, type(exc).__name__, exc)


def compute_window_hours(now: datetime | None = None) -> float:
    """Decide the fetch window in hours.

    有上次成功时间 -> now - last_success，封顶 48h、下限 1h；
    无状态文件 -> env DEFAULT_WINDOW_HOURS（默认 24）。
    """
    if now is None:
        now = datetime.now(timezone.utc)
    last_success = load_last_success()
    if last_success is None:
        return _default_window_hours()
    hours = (now - last_success).total_seconds() / 3600
    return min(max(hours, MIN_WINDOW_HOURS), MAX_WINDOW_HOURS)


def _default_window_hours() -> float:
    raw = os.environ.get("DEFAULT_WINDOW_HOURS", "").strip()
    if not raw:
        return FALLBACK_WINDOW_HOURS
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            "Invalid DEFAULT_WINDOW_HOURS=%r, falling back to %s", raw, FALLBACK_WINDOW_HOURS
        )
        return FALLBACK_WINDOW_HOURS
