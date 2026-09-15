"""Alert delivery stubs (email / webhook). In-API alerts are the real channel."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

from shared.models import Alert, Product, Watch

logger = logging.getLogger(__name__)


def deliver_alert(alert: Alert, product: Product, watch: Optional[Watch] = None) -> str:
    """Best-effort stub delivery. Always returns a status string; never raises."""
    payload = {
        "alert_id": alert.id,
        "product_url": product.product_url,
        "product_name": product.name,
        "old_price": alert.old_price,
        "new_price": alert.new_price,
        "currency": alert.currency,
        "direction": alert.direction,
        "message": alert.message,
        "alert_mode": watch.alert_mode if watch else None,
        "country": product.country,
    }

    email_to = os.getenv("ALERT_EMAIL_TO") or ""
    if email_to.strip():
        logger.info("EMAIL STUB → %s: %s", email_to, alert.message)
    else:
        logger.info("EMAIL STUB (no ALERT_EMAIL_TO configured): %s", alert.message)

    webhook_url = (os.getenv("ALERT_WEBHOOK_URL") or "").strip()
    if webhook_url:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.info("Webhook delivered status=%s", resp.status)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("Webhook stub failed: %s", exc)
            return "stubbed_webhook_failed"

    return "stubbed"
