"""Upsert products, record history, and emit in-API alerts on price changes."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from shared.countries import canonicalize_product_url, country_from_url
from shared.models import Alert, PriceHistory, Product, Watch, utcnow
from shared.notify import deliver_alert

logger = logging.getLogger(__name__)

PRICE_EPSILON = 0.005  # ignore sub-cent float noise


def _changed(old: Optional[float], new: float) -> bool:
    if old is None:
        return False
    return abs(float(old) - float(new)) > PRICE_EPSILON


def get_or_create_product(
    db: Session,
    product_url: str,
    *,
    name: Optional[str] = None,
    image_url: Optional[str] = None,
    country: Optional[str] = None,
) -> Product:
    url = canonicalize_product_url(product_url)
    product = db.query(Product).filter(Product.product_url == url).one_or_none()
    if product:
        if name and product.name in {"Unknown product", ""}:
            product.name = name
        if image_url and not product.image_url:
            product.image_url = image_url
        return product

    detected = country_from_url(url)
    code = (country or (detected.code if detected else "")).lower()
    if not code:
        raise ValueError(f"Cannot infer Jumia country from URL: {product_url}")

    product = Product(
        name=name or "Unknown product",
        current_price=None,
        currency=detected.currency if detected else None,
        image_url=image_url,
        product_url=url,
        country=code,
    )
    db.add(product)
    db.flush()
    return product


def apply_scrape_result(db: Session, data: dict) -> dict:
    """Apply one scrape payload: upsert product, maybe write history + alerts.

    Returns a summary dict for APIs/tests. Caller commits.
    """
    url = canonicalize_product_url(data["product_url"])
    new_price = float(data["price"])
    country = data.get("country")
    if not country:
        detected = country_from_url(url)
        country = detected.code if detected else None
    if not country:
        raise ValueError(f"Missing country for {url}")

    product = db.query(Product).filter(Product.product_url == url).one_or_none()
    created = product is None
    if product is None:
        product = Product(
            name=data.get("name") or "Unknown product",
            current_price=None,
            currency=data.get("currency"),
            image_url=data.get("image_url"),
            product_url=url,
            country=country,
            category=data.get("category"),
            sku=data.get("sku"),
        )
        db.add(product)
        db.flush()
    else:
        if data.get("name"):
            product.name = data["name"]
        if data.get("image_url"):
            product.image_url = data["image_url"]
        if data.get("currency"):
            product.currency = data["currency"]
        if data.get("category"):
            product.category = data["category"]
        if data.get("sku"):
            product.sku = data["sku"]
        product.country = country

    old_price = product.current_price
    first_observation = old_price is None
    price_changed = _changed(old_price, new_price)
    direction = None
    alerts_created: list[Alert] = []

    if first_observation or price_changed:
        history = PriceHistory(
            product_id=product.id,
            price=new_price,
            listed_price=data.get("old_price") or data.get("listed_price"),
            discount=data.get("discount"),
            currency=data.get("currency") or product.currency,
            recorded_at=utcnow(),
        )
        db.add(history)

    if price_changed and old_price is not None:
        direction = "up" if new_price > float(old_price) else "down"
        currency = data.get("currency") or product.currency or ""
        message = (
            f"Price {direction} from {currency} {old_price:g} to {currency} {new_price:g}"
        ).strip()
        watches = (
            db.query(Watch)
            .filter(Watch.product_id == product.id, Watch.is_active.is_(True))
            .all()
        )
        for watch in watches:
            if watch.alert_mode == "any_change" or watch.alert_mode == f"price_{direction}":
                alert = Alert(
                    watch_id=watch.id,
                    product_id=product.id,
                    old_price=float(old_price),
                    new_price=new_price,
                    currency=currency or None,
                    direction=direction,
                    message=message,
                    read=False,
                    delivery_status="pending",
                    created_at=utcnow(),
                )
                db.add(alert)
                db.flush()
                alert.delivery_status = deliver_alert(alert, product, watch)
                alerts_created.append(alert)

    product.current_price = new_price
    product.updated_at = utcnow()
    db.flush()

    logger.info(
        "Applied scrape url=%s created=%s first=%s changed=%s direction=%s alerts=%s",
        url,
        created,
        first_observation,
        price_changed,
        direction,
        len(alerts_created),
    )
    return {
        "product_id": product.id,
        "created": created,
        "first_observation": first_observation,
        "price_changed": price_changed,
        "direction": direction,
        "old_price": old_price,
        "new_price": new_price,
        "alerts_created": len(alerts_created),
        "alert_ids": [a.id for a in alerts_created],
    }
