"""Runtime knobs shared by API, scraper, and processor."""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


def check_interval_minutes() -> int:
    """How often each watched URL is eligible to be fetched.

    Prefer CHECK_INTERVAL_MINUTES; fall back to SCRAPE_INTERVAL_SECONDS / 60
    (legacy) then 15 minutes.
    """
    raw = os.getenv("CHECK_INTERVAL_MINUTES")
    if raw is not None and str(raw).strip() != "":
        return max(1, int(raw))
    seconds = _int_env("SCRAPE_INTERVAL_SECONDS", 900)
    return max(1, seconds // 60)


def check_interval_seconds() -> int:
    return check_interval_minutes() * 60


def history_retention_days() -> int:
    """Keep raw price_history points this many days, then downsample to daily.

    0 disables retention (never downsample or delete).
    """
    return max(0, _int_env("HISTORY_RETENTION_DAYS", 90))


def history_retention_interval_seconds() -> int:
    return max(60, _int_env("HISTORY_RETENTION_INTERVAL_SECONDS", 3600))
