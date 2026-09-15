from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.main import SessionLocal
from shared.models import PriceHistory, utcnow
from shared.monitor import get_or_create_product
from shared.retention import apply_history_retention
from shared.settings import check_interval_minutes, check_interval_seconds, history_retention_days


KE_URL = "https://www.jumia.co.ke/infinix-smart-8-64gb.html"
OLD_DAY = datetime(2024, 1, 15, tzinfo=timezone.utc)
OLDER_DAY = datetime(2023, 12, 1, tzinfo=timezone.utc)


def _add_at(db: Session, product_id: int, when: datetime, price: float) -> PriceHistory:
    row = PriceHistory(
        product_id=product_id,
        price=price,
        currency="KES",
        recorded_at=when,
    )
    db.add(row)
    db.flush()
    return row


def test_default_knobs():
    assert history_retention_days() == 90
    assert check_interval_minutes() == 15
    assert check_interval_seconds() == 900


def test_check_interval_minutes_env(monkeypatch):
    monkeypatch.setenv("CHECK_INTERVAL_MINUTES", "60")
    assert check_interval_minutes() == 60
    assert check_interval_seconds() == 3600


def test_retention_keeps_recent_raw_and_daily_downsamples_old():
    db: Session = SessionLocal()
    try:
        product = get_or_create_product(db, KE_URL, name="Infinix")
        db.commit()
        _add_at(db, product.id, OLD_DAY.replace(hour=8), 100)
        _add_at(db, product.id, OLD_DAY.replace(hour=12), 110)
        _add_at(db, product.id, OLD_DAY.replace(hour=16), 120)
        newest_old = _add_at(db, product.id, OLD_DAY.replace(hour=20), 130)
        other_day = _add_at(db, product.id, OLDER_DAY.replace(hour=10), 90)
        recent_a = _add_at(db, product.id, utcnow() - timedelta(days=10), 200)
        recent_b = _add_at(db, product.id, utcnow() - timedelta(days=1), 210)
        db.commit()

        summary = apply_history_retention(db, retention_days=90)
        db.commit()
        assert summary["skipped"] is False
        assert summary["deleted"] == 3
        assert summary["kept_daily"] == 2

        remaining = {row.id for row in db.query(PriceHistory).all()}
        assert remaining == {newest_old.id, other_day.id, recent_a.id, recent_b.id}
        kept_old = db.query(PriceHistory).filter(PriceHistory.id == newest_old.id).one()
        assert kept_old.price == 130
    finally:
        db.close()


def test_retention_disabled_when_zero_days():
    db: Session = SessionLocal()
    try:
        product = get_or_create_product(db, KE_URL, name="Infinix")
        _add_at(db, product.id, OLD_DAY.replace(hour=8), 1)
        _add_at(db, product.id, OLD_DAY.replace(hour=12), 2)
        db.commit()
        summary = apply_history_retention(db, retention_days=0)
        db.commit()
        assert summary["skipped"] is True
        assert db.query(PriceHistory).count() == 2
    finally:
        db.close()
