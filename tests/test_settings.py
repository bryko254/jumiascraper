"""Connection URL helpers for Railway + docker-compose fallbacks."""

from __future__ import annotations

import re

from shared.settings import (
    cors_allow_origins,
    cors_origin_regex,
    database_url,
    rabbitmq_url,
    redis_url,
)


def test_database_url_prefers_railway_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:secret@postgres.railway.internal:5432/railway",
    )
    monkeypatch.setenv("DB_HOST", "postgres")
    assert database_url() == "postgresql://postgres:secret@postgres.railway.internal:5432/railway"


def test_database_url_normalizes_postgres_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert database_url().startswith("postgresql://")
    assert "u:p@host:5432/db" in database_url()


def test_database_url_falls_back_to_compose_hostname(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.setenv("DB_USER", "jumia_user")
    monkeypatch.setenv("DB_PASSWORD", "changeme")
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "jumia_db")
    assert database_url() == "postgresql://jumia_user:changeme@postgres:5432/jumia_db"


def test_redis_url_prefers_plugin(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://default:s3cret@redis.railway.internal:6379")
    monkeypatch.setenv("REDIS_HOST", "redis")
    assert redis_url() == "redis://default:s3cret@redis.railway.internal:6379"


def test_redis_url_falls_back_to_compose_hostname(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6379")
    assert redis_url() == "redis://redis:6379/0"


def test_rabbitmq_url_prefers_amqp(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://jumia:pass@rabbitmq.railway.internal:5672/")
    monkeypatch.setenv("RABBITMQ_HOST", "rabbitmq")
    assert rabbitmq_url() == "amqp://jumia:pass@rabbitmq.railway.internal:5672/"


def test_amqp_url_alias(monkeypatch):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    monkeypatch.setenv("AMQP_URL", "amqp://a:b@host:5672/vhost")
    assert rabbitmq_url() == "amqp://a:b@host:5672/vhost"


def test_rabbitmq_url_falls_back_to_compose_hostname(monkeypatch):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    monkeypatch.delenv("AMQP_URL", raising=False)
    monkeypatch.delenv("CLOUDAMQP_URL", raising=False)
    monkeypatch.setenv("RABBITMQ_USER", "guest")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "guest")
    monkeypatch.setenv("RABBITMQ_HOST", "rabbitmq")
    monkeypatch.setenv("RABBITMQ_PORT", "5672")
    assert rabbitmq_url() == "amqp://guest:guest@rabbitmq:5672/"


def test_rabbitmq_url_encodes_special_password(monkeypatch):
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    monkeypatch.delenv("AMQP_URL", raising=False)
    monkeypatch.delenv("CLOUDAMQP_URL", raising=False)
    monkeypatch.setenv("RABBITMQ_USER", "user")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "p@ss:w/d")
    monkeypatch.setenv("RABBITMQ_HOST", "rabbitmq")
    url = rabbitmq_url()
    assert "p%40ss%3Aw%2Fd" in url
    assert "@rabbitmq:5672" in url


def test_cors_origins_default_star(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert cors_allow_origins() == ["*"]


def test_cors_origins_csv(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert cors_allow_origins() == ["https://a.example", "https://b.example"]


def test_cors_origin_regex_matches_chrome_extension():
    pattern = re.compile(cors_origin_regex())
    origin = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef"
    assert pattern.fullmatch(origin)


def test_dockerfiles_build_from_repo_root():
    for path in ("api/Dockerfile", "scraper/Dockerfile", "processor/Dockerfile"):
        text = open(path, encoding="utf-8").read()
        assert "COPY shared /app/shared" in text
        service = path.split("/")[0]
        assert f"COPY {service} /app/{service}" in text


def test_api_dockerfile_listens_on_railway_port():
    text = open("api/Dockerfile", encoding="utf-8").read()
    assert "${PORT:-8000}" in text


def test_rabbitmq_parameters_parse_url(monkeypatch):
    monkeypatch.setenv("RABBITMQ_URL", "amqp://jumia:pass@rmq.railway.internal:5672/")
    from shared.queue import rabbitmq_parameters

    params = rabbitmq_parameters()
    assert params.host == "rmq.railway.internal"
    assert params.port == 5672
    assert params.credentials.username == "jumia"
