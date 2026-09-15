"""Single source of truth for the monitor schema."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, default="Unknown product")
    current_price = Column(Float, nullable=True)
    currency = Column(String(8), nullable=True)
    image_url = Column(String, nullable=True)
    product_url = Column(String, unique=True, nullable=False, index=True)
    country = Column(String(2), nullable=False, index=True)
    category = Column(String, nullable=True)
    sku = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    price_histories = relationship(
        "PriceHistory",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    watches = relationship("Watch", back_populates="product", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="product")


class PriceHistory(Base):
    __tablename__ = "price_histories"
    __table_args__ = (
        Index("ix_price_histories_product_recorded", "product_id", "recorded_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(Float, nullable=False)
    listed_price = Column(Float, nullable=True)
    discount = Column(String, nullable=True)
    currency = Column(String(8), nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    product = relationship("Product", back_populates="price_histories")


class Watch(Base):
    __tablename__ = "watches"
    __table_args__ = (
        UniqueConstraint("product_id", "alert_mode", name="uq_watch_product_mode"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_mode = Column(String(32), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    product = relationship("Product", back_populates="watches")
    alerts = relationship("Alert", back_populates="watch")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(Integer, ForeignKey("watches.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    old_price = Column(Float, nullable=False)
    new_price = Column(Float, nullable=False)
    currency = Column(String(8), nullable=True)
    direction = Column(String(8), nullable=False)  # up | down
    message = Column(Text, nullable=False)
    read = Column(Boolean, nullable=False, default=False)
    delivery_status = Column(String(32), nullable=False, default="stubbed")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    watch = relationship("Watch", back_populates="alerts")
    product = relationship("Product", back_populates="alerts")
