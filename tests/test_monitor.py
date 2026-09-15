from sqlalchemy.orm import Session

from api.main import SessionLocal
from shared.models import Alert, PriceHistory, Product, Watch
from shared.monitor import apply_scrape_result, get_or_create_product


KE_URL = "https://www.jumia.co.ke/infinix-smart-8-64gb.html"
NG_URL = "https://www.jumia.com.ng/tecno-spark-20.html"


def _payload(url, price, name="Phone", country="ke", currency="KES"):
    return {
        "product_url": url,
        "name": name,
        "price": price,
        "currency": currency,
        "country": country,
        "image_url": "https://example.test/p.jpg",
    }


def test_upsert_same_url_does_not_duplicate():
    db: Session = SessionLocal()
    try:
        apply_scrape_result(db, _payload(KE_URL, 1000, "A"))
        apply_scrape_result(db, _payload(KE_URL, 1000, "A updated"))
        db.commit()
        assert db.query(Product).count() == 1
        product = db.query(Product).one()
        assert product.name == "A updated"
        assert product.current_price == 1000
        # first observation writes history; unchanged price does not duplicate
        assert db.query(PriceHistory).count() == 1
    finally:
        db.close()


def test_price_down_watch_creates_alert_price_up_does_not():
    db: Session = SessionLocal()
    try:
        product = get_or_create_product(db, KE_URL, name="Infinix")
        db.add(Watch(product_id=product.id, alert_mode="price_down"))
        db.add(Watch(product_id=product.id, alert_mode="price_up"))
        db.commit()

        apply_scrape_result(db, _payload(KE_URL, 11200, "Infinix"))
        db.commit()
        assert db.query(Alert).count() == 0

        apply_scrape_result(db, _payload(KE_URL, 9800, "Infinix"))
        db.commit()
        alerts = db.query(Alert).all()
        assert len(alerts) == 1
        assert alerts[0].direction == "down"
        assert alerts[0].old_price == 11200
        assert alerts[0].new_price == 9800
        assert alerts[0].delivery_status == "stubbed"
        assert db.query(PriceHistory).count() == 2
    finally:
        db.close()


def test_any_change_fires_on_increase():
    db: Session = SessionLocal()
    try:
        product = get_or_create_product(db, NG_URL, name="Tecno")
        db.add(Watch(product_id=product.id, alert_mode="any_change"))
        db.commit()
        apply_scrape_result(db, _payload(NG_URL, 100, "Tecno", "ng", "NGN"))
        apply_scrape_result(db, _payload(NG_URL, 150, "Tecno", "ng", "NGN"))
        db.commit()
        alert = db.query(Alert).one()
        assert alert.direction == "up"
        assert "150" in alert.message
    finally:
        db.close()
