"""Price-history retention: raw window, then one point per UTC day."""

from __future__ import annotations

import logging
from datetime import timedelta, timezone

from sqlalchemy.orm import Session

from shared.models import PriceHistory, utcnow
from shared.settings import history_retention_days

logger = logging.getLogger(__name__)

_DELETE_CHUNK = 1000


def apply_history_retention(
    db: Session,
    *,
    retention_days: int | None = None,
) -> dict:
    """Keep all points newer than ``retention_days``; older days keep the last row.

    Does not bound total age: after the raw window, growth is ~1 row per
    product per day. Set HISTORY_RETENTION_DAYS=0 to skip.
    """
    days = history_retention_days() if retention_days is None else max(0, int(retention_days))
    if days <= 0:
        logger.info("History retention skipped (HISTORY_RETENTION_DAYS=%s)", days)
        return {"skipped": True, "retention_days": days, "deleted": 0, "kept_daily": 0, "examined": 0}

    cutoff = utcnow() - timedelta(days=days)
    old_rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.recorded_at < cutoff)
        .order_by(PriceHistory.product_id.asc(), PriceHistory.recorded_at.asc(), PriceHistory.id.asc())
        .all()
    )
    keep_ids: set[int] = set()
    buckets: dict[tuple[int, object], int] = {}
    for row in old_rows:
        recorded = row.recorded_at
        if recorded.tzinfo is None:
            day = recorded.date()
        else:
            day = recorded.astimezone(timezone.utc).date()
        buckets[(row.product_id, day)] = row.id
    keep_ids = set(buckets.values())
    delete_ids = [row.id for row in old_rows if row.id not in keep_ids]

    for start in range(0, len(delete_ids), _DELETE_CHUNK):
        chunk = delete_ids[start : start + _DELETE_CHUNK]
        (
            db.query(PriceHistory)
            .filter(PriceHistory.id.in_(chunk))
            .delete(synchronize_session=False)
        )

    summary = {
        "skipped": False,
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "examined": len(old_rows),
        "kept_daily": len(keep_ids),
        "deleted": len(delete_ids),
    }
    logger.info("History retention %s", summary)
    return summary
