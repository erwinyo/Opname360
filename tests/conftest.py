from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from opname360.core.db import get_session
from opname360.main import app


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    # Not used as a context manager, so the lifespan (real DB setup) doesn't run.
    yield TestClient(app)
    app.dependency_overrides.clear()
