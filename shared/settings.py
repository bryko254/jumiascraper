"""Runtime knobs shared by API, scraper, and processor.

Connection settings accept Railway-injected URLs (DATABASE_URL, REDIS_URL,
RABBITMQ_URL / AMQP_URL) and fall back to docker-compose hostnames
(postgres, redis, rabbitmq) plus DB_*/RABBITMQ_*/REDIS_* parts.
"""

from __future__ import annotations

import os
from urllib.parse import quote


def _env(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip()


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


def ingest_enabled() -> bool:
    return _env("ENABLE_INGEST", "true").lower() in {"1", "true", "yes"}


def ingest_token() -> str:
    return _env("INGEST_TOKEN", "dev-ingest-token") or "dev-ingest-token"


def database_url() -> str:
    """SQLAlchemy URL. Prefer DATABASE_URL (Railway Postgres plugin)."""
    explicit = _env("DATABASE_URL") or _env("POSTGRES_URL")
    if explicit:
        if explicit.startswith("postgres://"):
            return "postgresql://" + explicit[len("postgres://") :]
        return explicit
    user = _env("DB_USER", "jumia_user") or "jumia_user"
    password = os.getenv("DB_PASSWORD", "changeme")
    host = _env("DB_HOST", "postgres") or "postgres"
    port = _env("DB_PORT", "5432") or "5432"
    name = _env("DB_NAME", "jumia_db") or "jumia_db"
    return f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{name}"


def redis_url() -> str:
    """redis-py URL. Prefer REDIS_URL (Railway Redis plugin)."""
    explicit = _env("REDIS_URL")
    if explicit:
        return explicit
    host = _env("REDIS_HOST", "redis") or "redis"
    port = _env("REDIS_PORT", "6379") or "6379"
    db = _env("REDIS_DB", "0") or "0"
    password = os.getenv("REDIS_PASSWORD")
    user = _env("REDIS_USER", "") or ""
    scheme = _env("REDIS_SCHEME", "redis") or "redis"
    if password:
        auth = f"{quote(user, safe='')}:{quote(password, safe='')}@"
        return f"{scheme}://{auth}{host}:{port}/{db}"
    return f"{scheme}://{host}:{port}/{db}"


def rabbitmq_url() -> str:
    """AMQP URL. Prefer RABBITMQ_URL / AMQP_URL; else compose from RABBITMQ_*."""
    explicit = _env("RABBITMQ_URL") or _env("AMQP_URL") or _env("CLOUDAMQP_URL")
    if explicit:
        return explicit
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    host = _env("RABBITMQ_HOST", "rabbitmq") or "rabbitmq"
    port = _env("RABBITMQ_PORT", "5672") or "5672"
    vhost = _env("RABBITMQ_VHOST", "/") or "/"
    if not vhost.startswith("/"):
        vhost = "/" + vhost
    # vhost "/" must be encoded as %2F when more than the trailing slash is needed;
    # pika URLParameters accepts amqp://user:pass@host:port/ and .../%2F.
    vhost_q = quote(vhost, safe="/")
    if vhost_q == "/":
        vhost_q = "/"
    return (
        f"amqp://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}{vhost_q}"
    )


def cors_allow_origins() -> list[str]:
    """Explicit browser origins. ``*`` (default) allows any origin.

    Chrome extension pages are always covered separately via
    :func:`cors_origin_regex`. Set CORS_ORIGINS to a comma-separated list in
    production if you want to drop the wildcard (for example your custom
    domain). ``chrome-extension://*`` in this list is ignored — use the regex.
    """
    raw = os.getenv("CORS_ORIGINS")
    if raw is None or str(raw).strip() == "":
        return ["*"]
    parts = [p.strip() for p in str(raw).split(",") if p.strip() and p.strip() != "chrome-extension://*"]
    if not parts or "*" in parts:
        return ["*"]
    return parts


def cors_origin_regex() -> str:
    """Always allow ``chrome-extension://<id>``; optional extra CORS_ORIGIN_REGEX."""
    extra = _env("CORS_ORIGIN_REGEX")
    base = r"chrome-extension://.*"
    if extra:
        return rf"({base})|({extra})"
    return base


def db_wait_attempts() -> int:
    return max(1, _int_env("DB_WAIT_ATTEMPTS", 30))


def db_wait_delay_seconds() -> float:
    return max(0.1, float(_env("DB_WAIT_DELAY_SECONDS", "1") or "1"))
