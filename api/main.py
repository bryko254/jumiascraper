"""FastAPI application for the Jumia price monitor."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from shared.countries import (
    ALERT_MODES,
    canonicalize_product_url,
    countries_payload,
    country_from_url,
)
from shared.database import init_db, make_engine, make_session_factory, wait_for_db
from shared.models import Alert, PriceHistory, Product, Watch
from shared.monitor import apply_scrape_result, get_or_create_product
from shared.parser import parse_product_html
from shared.retention import apply_history_retention
from shared.settings import (
    check_interval_minutes,
    cors_allow_origins,
    cors_origin_regex,
    history_retention_days,
    ingest_enabled,
    ingest_token,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")

engine = make_engine()
SessionLocal = make_session_factory(engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    wait_for_db(engine)
    init_db(engine)
    logger.info("API ready")
    yield


app = FastAPI(
    title="Jumia Price Monitor API",
    description="Watch Jumia products across 8 countries and receive in-API price alerts.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(),
    allow_origin_regex=cors_origin_regex(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- schemas ----------


class WatchCreate(BaseModel):
    product_url: str
    alert_mode: str = "any_change"
    name: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator("product_url")
    @classmethod
    def _url(cls, value: str) -> str:
        value = canonicalize_product_url(value)
        if country_from_url(value) is None:
            raise ValueError("URL is not a supported Jumia storefront")
        return value

    @field_validator("alert_mode")
    @classmethod
    def _mode(cls, value: str) -> str:
        if value not in ALERT_MODES:
            raise ValueError(f"alert_mode must be one of {ALERT_MODES}")
        return value


class ProductOut(BaseModel):
    id: int
    name: str
    current_price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    product_url: str
    country: str
    category: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class WatchOut(BaseModel):
    id: int
    alert_mode: str
    is_active: bool
    created_at: Optional[str] = None
    product: ProductOut


class HistoryOut(BaseModel):
    id: int
    product_id: int
    price: float
    listed_price: Optional[float] = None
    discount: Optional[str] = None
    currency: Optional[str] = None
    recorded_at: Optional[str] = None


class AlertOut(BaseModel):
    id: int
    watch_id: Optional[int] = None
    product_id: int
    product_name: Optional[str] = None
    product_url: Optional[str] = None
    old_price: float
    new_price: float
    currency: Optional[str] = None
    direction: str
    message: str
    read: bool
    delivery_status: str
    created_at: Optional[str] = None


class AlertPatch(BaseModel):
    read: bool = True


class IngestBody(BaseModel):
    product_url: str
    name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    old_price: Optional[float] = None
    discount: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    sku: Optional[str] = None
    html: Optional[str] = Field(default=None, description="Optional fixture HTML to parse")


# ---------- serializers ----------


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def serialize_product(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "current_price": p.current_price,
        "currency": p.currency,
        "image_url": p.image_url,
        "product_url": p.product_url,
        "country": p.country,
        "category": p.category,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


def serialize_watch(w: Watch) -> dict:
    return {
        "id": w.id,
        "alert_mode": w.alert_mode,
        "is_active": w.is_active,
        "created_at": _iso(w.created_at),
        "product": serialize_product(w.product),
    }


def serialize_alert(a: Alert) -> dict:
    product = a.product
    return {
        "id": a.id,
        "watch_id": a.watch_id,
        "product_id": a.product_id,
        "product_name": product.name if product else None,
        "product_url": product.product_url if product else None,
        "old_price": a.old_price,
        "new_price": a.new_price,
        "currency": a.currency,
        "direction": a.direction,
        "message": a.message,
        "read": a.read,
        "delivery_status": a.delivery_status,
        "created_at": _iso(a.created_at),
    }


def serialize_history(h: PriceHistory) -> dict:
    return {
        "id": h.id,
        "product_id": h.product_id,
        "price": h.price,
        "listed_price": h.listed_price,
        "discount": h.discount,
        "currency": h.currency,
        "recorded_at": _iso(h.recorded_at),
    }


def require_ingest_token(x_ingest_token: Optional[str] = Header(default=None)) -> None:
    if not ingest_enabled():
        raise HTTPException(status_code=403, detail="Fixture ingest is disabled")
    expected = ingest_token()
    if not x_ingest_token or x_ingest_token != expected:
        raise HTTPException(status_code=401, detail="Invalid ingest token")


# ---------- routes ----------


@app.get("/")
def root():
    return {
        "message": "Jumia Price Monitor API",
        "docs": "/docs",
        "countries": [c["code"] for c in countries_payload()],
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        watches = db.query(Watch).count()
        products = db.query(Product).count()
        alerts = db.query(Alert).count()
        history_rows = db.query(PriceHistory).count()
        return {
            "status": "healthy",
            "database": "connected",
            "watches": watches,
            "products": products,
            "alerts": alerts,
            "price_histories": history_rows,
            "storage": {
                "postgres": "primary",
                "redis": "short_ttl_scrape_cache",
                "rabbitmq": "ephemeral_queue",
                "history_retention_days": history_retention_days(),
                "check_interval_minutes": check_interval_minutes(),
            },
            "message": "API is functioning normally",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/countries")
def list_countries():
    return countries_payload()


@app.post("/watches", status_code=201)
def create_watch(body: WatchCreate, db: Session = Depends(get_db)):
    country = country_from_url(body.product_url)
    product = get_or_create_product(
        db,
        body.product_url,
        name=body.name,
        image_url=body.image_url,
        country=country.code if country else None,
    )
    existing = (
        db.query(Watch)
        .filter(Watch.product_id == product.id, Watch.alert_mode == body.alert_mode)
        .one_or_none()
    )
    if existing:
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return serialize_watch(existing)

    watch = Watch(product_id=product.id, alert_mode=body.alert_mode, is_active=True)
    db.add(watch)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        watch = (
            db.query(Watch)
            .filter(Watch.product_id == product.id, Watch.alert_mode == body.alert_mode)
            .one()
        )
        return serialize_watch(watch)
    db.refresh(watch)
    return serialize_watch(watch)


@app.get("/watches")
def list_watches(
    skip: int = 0,
    limit: int = 100,
    country: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Watch).options(joinedload(Watch.product)).filter(Watch.is_active.is_(True))
    if country:
        query = query.join(Product).filter(Product.country == country.lower())
    watches = query.order_by(Watch.created_at.desc()).offset(skip).limit(min(limit, 200)).all()
    return [serialize_watch(w) for w in watches]


@app.get("/watches/{watch_id}")
def get_watch(watch_id: int, db: Session = Depends(get_db)):
    watch = db.query(Watch).options(joinedload(Watch.product)).filter(Watch.id == watch_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    return serialize_watch(watch)


@app.delete("/watches/{watch_id}", status_code=204)
def delete_watch(watch_id: int, db: Session = Depends(get_db)):
    watch = db.query(Watch).filter(Watch.id == watch_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    db.delete(watch)
    db.commit()
    return None


@app.get("/products/")
@app.get("/products")
def list_products(
    skip: int = 0,
    limit: int = 100,
    country: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if country:
        query = query.filter(Product.country == country.lower())
    products = query.order_by(Product.updated_at.desc()).offset(skip).limit(min(limit, 200)).all()
    return [serialize_product(p) for p in products]


@app.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_product(product)


@app.get("/products/{product_id}/history")
def product_history(
    product_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.recorded_at.desc())
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )
    return [serialize_history(h) for h in rows]


@app.get("/alerts")
def list_alerts(
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Alert).options(joinedload(Alert.product))
    if unread_only:
        query = query.filter(Alert.read.is_(False))
    alerts = query.order_by(Alert.created_at.desc()).offset(skip).limit(min(limit, 200)).all()
    return [serialize_alert(a) for a in alerts]


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).options(joinedload(Alert.product)).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return serialize_alert(alert)


@app.patch("/alerts/{alert_id}")
def patch_alert(alert_id: int, body: AlertPatch, db: Session = Depends(get_db)):
    alert = db.query(Alert).options(joinedload(Alert.product)).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.read = body.read
    db.commit()
    db.refresh(alert)
    return serialize_alert(alert)


@app.post("/alerts/mark-all-read")
def mark_all_read(db: Session = Depends(get_db)):
    updated = db.query(Alert).filter(Alert.read.is_(False)).update({Alert.read: True})
    db.commit()
    return {"updated": updated}


@app.post("/internal/ingest")
def ingest(
    body: IngestBody,
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
):
    """Apply a fixture scrape result (tests / local demo). Does not hit Jumia."""
    data = body.model_dump()
    html = data.pop("html", None)
    if html:
        parsed = parse_product_html(html, body.product_url)
        if not parsed:
            raise HTTPException(status_code=422, detail="Could not parse product HTML")
        data = {**parsed, **{k: v for k, v in data.items() if v is not None}}
    if data.get("price") is None:
        raise HTTPException(status_code=422, detail="price is required (or provide parseable html)")
    try:
        summary = apply_scrape_result(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return summary


@app.post("/internal/retain")
def retain_history(
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
):
    """Downsample price_history older than HISTORY_RETENTION_DAYS (ops / tests)."""
    summary = apply_history_retention(db)
    db.commit()
    return summary
