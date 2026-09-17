"""Engine / session helpers used by API, processor, and scraper."""

from __future__ import annotations

import time
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from shared.models import Base
from shared.settings import database_url, db_wait_attempts, db_wait_delay_seconds


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    kwargs = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url in {"sqlite://", "sqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def wait_for_db(
    engine: Engine,
    attempts: int | None = None,
    delay: float | None = None,
) -> None:
    attempts = db_wait_attempts() if attempts is None else attempts
    delay = db_wait_delay_seconds() if delay is None else delay
    last_error = None
    for _ in range(attempts):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - startup retry
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"Database not ready: {last_error}")


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


def session_scope(SessionLocal: sessionmaker) -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
