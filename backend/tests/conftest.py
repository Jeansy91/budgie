import os
from pathlib import Path

os.environ.setdefault("BUDGIE_DATABASE_URL", "postgresql+psycopg://postgres@/budgie_test?host=/tmp&port=5433")
os.environ["BUDGIE_COOKIE_SECURE"] = "false"
os.environ.setdefault("BUDGIE_SECRET_KEY", "nur-fuer-tests-0123456789")
os.environ.setdefault("BUDGIE_FINTS_PRODUCT_ID", "TESTPRODUKT")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import models
from app.ai import service as ai_service
from app.db import engine
from app.main import app

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="session", autouse=True)
def schema():
    models.Base.metadata.drop_all(engine)
    models.Base.metadata.create_all(engine)
    yield
    models.Base.metadata.drop_all(engine)


# In tests, AI training and the language model run immediately instead of in the background
ai_service.SYNC = True


@pytest.fixture(autouse=True)
def clean():
    yield
    ai_service._cache.clear()
    tables = ", ".join(t.name for t in models.Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin(client):
    r = client.post(
        "/api/auth/setup",
        json={"household_name": "Familie Test", "username": "alex", "display_name": "Alex", "password": "geheim123"},
    )
    assert r.status_code == 201, r.text
    return client


@pytest.fixture
def no_ai(monkeypatch):
    """For tests that only look at rules: AI categorization disabled."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_enabled", False)


@pytest.fixture
def sample_csv() -> bytes:
    return (DATA / "ing_beispiel.csv").read_bytes()


def find_category(client, main: str, sub: str | None = None) -> int:
    for c in client.get("/api/categories").json():
        if c["name"] == main:
            if sub is None:
                return c["id"]
            return next(ch["id"] for ch in c["children"] if ch["name"] == sub)
    raise KeyError(main)
