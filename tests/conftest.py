import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_INGEST", "true")
os.environ.setdefault("INGEST_TOKEN", "test-token")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

import pytest
from fastapi.testclient import TestClient

from api.main import app, engine
from shared.models import Base


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def ingest_headers():
    return {"X-Ingest-Token": "test-token"}
