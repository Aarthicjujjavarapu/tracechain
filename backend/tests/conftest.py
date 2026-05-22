"""
Shared test fixtures.

Uses an in-memory SQLite database so tests run without a real Postgres instance.
The `get_db` FastAPI dependency is overridden per-test to use the SQLite session.

IMPORTANT: PostgreSQL-specific column types (JSONB, UUID) are patched to
SQLite-compatible equivalents at *import time* — before any mapper is
configured — so that the SQLAlchemy ORM sees consistent types throughout
the process lifetime.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Patch types before models are mapped ─────────────────────────────────────
# Import Base first so metadata exists, then patch before any mapper call.
from app.database import Base, get_db  # noqa: E402  (must come before model import)

def _patch_pg_types_for_sqlite():
    """Replace PostgreSQL column types with SQLite-compatible equivalents."""
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, UUID):
                col.type = String(36)

# Import models (this triggers mapper configuration).  Types are patched
# immediately afterward so they are stable for all subsequent fixtures.
import app.models  # noqa: F401, E402
_patch_pg_types_for_sqlite()

from app.main import app  # noqa: E402 (must come after models are imported)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
