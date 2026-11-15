from collections.abc import Iterator

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from .database import rebuild

from opname360.core.config import settings
from opname360.core.db import get_session
from opname360.core.security import hash_password
from opname360.main import app
from opname360.models import Role, User


PASSWORD = 'rahasia-123'


@pytest.fixture(scope='session')
def engine() -> Iterator[Engine]:
    """The test database, rebuilt from the real migrations once per run."""
    assert settings.test_database_url, 'Set TEST_DATABASE_URL in .env'
    rebuild(settings.test_database_url)
    engine = create_engine(settings.test_database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session whose commits are undone when the test ends."""
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            connection, join_transaction_mode='create_savepoint'
        ) as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(
    session: Session, username: str, role: Role, *, is_active: bool = True
) -> User:
    user = User(
        username=username,
        full_name=username.title(),
        role=role,
        is_active=is_active,
        password_hash=hash_password(PASSWORD),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def sign_in(client: TestClient, username: str, password: str = PASSWORD):
    return client.post(
        '/api/v1/auth/login', json={'username': username, 'password': password}
    )


@pytest.fixture
def owner(session: Session) -> User:
    return make_user(session, 'owner', Role.owner)


@pytest.fixture
def owner_client(client: TestClient, owner: User) -> TestClient:
    assert sign_in(client, owner.username).status_code == 200
    return client
