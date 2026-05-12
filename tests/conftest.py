"""Shared test fixtures for all test modules."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base
from app.database import get_db

# Single shared in-memory engine — StaticPool keeps all sessions on the same
# underlying connection so tables created in the fixture are visible everywhere.
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_db():
    db = Session(bind=TEST_ENGINE)
    try:
        yield db
    finally:
        db.close()


# Register the override once at import time
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)
