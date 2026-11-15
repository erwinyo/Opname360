from collections.abc import Iterator
from itertools import count

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from .database import rebuild

from opname360.core.config import settings
from opname360.core.db import get_session
from opname360.core.security import hash_password
from opname360.main import app
from opname360.models import Role, Sku, User


PASSWORD = 'rahasia-123'
_names = count(1)


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


def new_category(
    client: TestClient,
    name: str = 'Seragam',
    sub_categories: tuple[str, ...] = ('Kemeja',),
    costing_method: str = 'moving_average',
) -> dict:
    """Create a Category through the API and return it with its subs."""
    category = client.post(
        '/api/v1/categories/',
        json={'name': name, 'costing_method': costing_method},
    ).json()
    for sub_category in sub_categories:
        category = client.post(
            f'/api/v1/categories/{category["id"]}/sub-categories',
            json={'name': sub_category},
        ).json()
    return category


def sku_row(**fields: object) -> dict:
    return {'size': '10', 'selling_price': 85000, **fields}


def new_product(
    client: TestClient,
    sub_category_id: int,
    name: str = 'Kemeja Putih SD',
    skus: list[dict] | None = None,
) -> dict:
    response = client.post(
        '/api/v1/products/',
        json={
            'name': name,
            'sub_category_id': sub_category_id,
            'skus': skus or [sku_row()],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def new_sku(
    client: TestClient,
    session: Session,
    costing_method: str = 'moving_average',
    **sku_fields: object,
) -> Sku:
    """A SKU in its own Category with the given Costing Method."""
    name = f'{costing_method}-{next(_names)}'
    category = new_category(client, name, ('Sub',), costing_method)
    product = new_product(
        client,
        category['sub_categories'][0]['id'],
        f'Produk {name}',
        [sku_row(**sku_fields)],
    )
    sku = session.get(Sku, product['skus'][0]['id'])
    assert sku is not None
    return sku


def new_supplier(client: TestClient, name: str = 'CV Sumber Jaya') -> dict:
    response = client.post('/api/v1/suppliers/', json={'name': name})
    assert response.status_code == 201, response.text
    return response.json()


def new_receipt(
    client: TestClient,
    supplier_id: int,
    lines: list[dict],
    *,
    complete: bool = True,
    **header: object,
) -> dict:
    """A Goods Receipt through the API, completed unless told otherwise."""
    response = client.post(
        '/api/v1/goods-receipts/',
        json={
            'supplier_id': supplier_id,
            'received_on': '2026-11-15',
            'lines': lines,
            **header,
        },
    )
    assert response.status_code == 201, response.text
    receipt = response.json()
    if complete:
        response = client.post(
            f'/api/v1/goods-receipts/{receipt["id"]}/complete'
        )
        assert response.status_code == 200, response.text
        receipt = response.json()
    return receipt
