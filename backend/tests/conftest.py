"""Shared pytest fixtures for backend tests."""
from __future__ import annotations

import io
import os
import pytest

# Set env vars BEFORE any app imports so pydantic-settings picks them up
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEMO_MODE"] = "true"
os.environ["SESSION_SECRET"] = "test-secret-key-for-pytest-only"
os.environ["OIDC_DISCOVERY_URL"] = ""
os.environ["OIDC_CLIENT_ID"] = "test-client"
os.environ["UPLOAD_DIR"] = "/tmp/curator-test-uploads"

# Patch settings directly in case the module was already loaded
from app.core.config import settings  # noqa: E402
settings.DEMO_MODE = True
settings.DATABASE_URL = "sqlite:///:memory:"
settings.SESSION_SECRET = "test-secret-key-for-pytest-only"
settings.OIDC_DISCOVERY_URL = ""
settings.UPLOAD_DIR = "/tmp/curator-test-uploads"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

# Import models so Base.metadata has the table definitions
from app.core import database as _db_module  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.models import image, dataset, audit  # noqa: E402, F401
from app.main import app  # noqa: E402

# Replace the module-level engine and session with a single shared in-memory
# engine so that both init_db() (called in lifespan) and route handlers work
# against the same database.
SHARED_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
SharedSession = sessionmaker(bind=SHARED_ENGINE, autocommit=False, autoflush=False)

# Patch the database module so lifespan's init_db() uses our engine
_db_module.engine = SHARED_ENGINE
_db_module.SessionLocal = SharedSession


@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=SHARED_ENGINE)
    yield
    Base.metadata.drop_all(bind=SHARED_ENGINE)


def override_get_db():
    db = SharedSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client() -> TestClient:
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def make_png_bytes(width: int = 64, height: int = 64) -> bytes:
    """Generate a minimal valid PNG in memory."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg_bytes(width: int = 64, height: int = 64) -> bytes:
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
