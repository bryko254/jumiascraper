#!/usr/bin/env python3
"""Fixture smoke: watch → mock price drop → in-API alert (no live Jumia)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_INGEST", "true")
os.environ.setdefault("INGEST_TOKEN", "test-token")

from fastapi.testclient import TestClient

from api.main import app
from tests.html_samples import load_fixture

KE_URL = "https://www.jumia.co.ke/infinix-smart-8-64gb.html"


def main() -> int:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        watch = client.post(
            "/watches",
            json={"product_url": KE_URL, "alert_mode": "price_down", "name": "Infinix Smart 8"},
        )
        assert watch.status_code == 201, watch.text
        headers = {"X-Ingest-Token": "test-token"}
        first = client.post(
            "/internal/ingest",
            headers=headers,
            json={"product_url": KE_URL, "html": load_fixture("product_ke.html")},
        )
        assert first.status_code == 200 and first.json()["alerts_created"] == 0, first.text
        second = client.post(
            "/internal/ingest",
            headers=headers,
            json={"product_url": KE_URL, "html": load_fixture("product_ke_drop.html")},
        )
        assert second.status_code == 200 and second.json()["alerts_created"] == 1, second.text
        alerts = client.get("/alerts").json()
        assert alerts[0]["direction"] == "down"
        print("SMOKE OK")
        print(f"  watch_id={watch.json()['id']}")
        print(f"  {alerts[0]['message']}")
        print(f"  delivery_status={alerts[0]['delivery_status']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
