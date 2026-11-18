from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
    tracks_batches: bool = False,
) -> dict:
    """Create a Category through the API and return it with its subs."""
    category = client.post(
        '/api/v1/categories/',
        json={
            'name': name,
            'costing_method': costing_method,
            'tracks_batches': tracks_batches,
        },
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


def new_medicine(
    client: TestClient, session: Session, costing_method: str = 'fifo'
) -> Sku:
    """A SKU in its own Category that tracks Batches (slice 6)."""
    name = f'Obat-{next(_names)}'
    category = new_category(
        client, name, ('Sub',), costing_method, tracks_batches=True
    )
    product = new_product(
        client,
        category['sub_categories'][0]['id'],
        f'Pil {name}',
        [sku_row(size=None, stock_unit='botol', selling_price=50000)],
    )
    sku = session.get(Sku, product['skus'][0]['id'])
    assert sku is not None
    return sku


def expiry(days: int) -> str:
    """A date `days` from today's Shop Day."""
    from opname360.services.documents import shop_now

    return str(shop_now().date() + timedelta(days=days))


def batch_line(
    sku_id: int | None,
    quantity: float,
    unit_cost: float,
    batch_number: str,
    expires_on: str,
) -> dict:
    return {
        **receipt_line(sku_id, quantity, unit_cost),
        'batch_number': batch_number,
        'expires_on': expires_on,
    }


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


def receipt_line(
    sku_id: int | None, quantity: float, unit_cost: float
) -> dict:
    return {'sku_id': sku_id, 'quantity': quantity, 'unit_cost': unit_cost}


def stock_of(
    client: TestClient, sku_id: int | None
) -> tuple[Decimal, Decimal]:
    """The SKU's System Quantity and Stock Value, read from its Stock Card."""
    card = client.get(f'/api/v1/stock/skus/{sku_id}/card').json()
    return Decimal(card['sku']['quantity']), Decimal(card['sku']['value'])


OPNAMES = '/api/v1/opnames/'
COUNTING = '/api/v1/counting/'


def switch_to(client: TestClient, user: User) -> TestClient:
    """Sign the test client in as someone else."""
    assert sign_in(client, user.username).status_code == 200
    return client


def receive(
    client: TestClient, sku: Sku, quantity: float, unit_cost: float
) -> None:
    """Stock in through a completed Goods Receipt from a fresh Supplier."""
    supplier = new_supplier(client, f'Pemasok {next(_names)}')
    new_receipt(
        client, supplier['id'], [receipt_line(sku.id, quantity, unit_cost)]
    )


def open_opname(
    client: TestClient, checkers: list[User], **body: object
) -> dict:
    response = client.post(
        OPNAMES,
        json={'checker_ids': [user.id for user in checkers], **body},
    )
    assert response.status_code == 201, response.text
    return response.json()


def count(client: TestClient, opname_id: int, **body: object):
    """One Count Entry: `code=` a scan or `sku_id=`, with `quantity=`."""
    return client.post(f'{COUNTING}{opname_id}/entries', json=body)


def lines_of(client: TestClient, opname_id: int, **query: object) -> list:
    response = client.get(
        f'{OPNAMES}{opname_id}/lines', params={'limit': 2000, **query}
    )
    assert response.status_code == 200, response.text
    return response.json()['items']


SHIFTS = '/api/v1/shifts/'


def open_shift(client: TestClient, opening_float: int = 200000) -> dict:
    """Open the drawer's Shift as whoever the client is signed in as."""
    response = client.post(SHIFTS, json={'opening_float': opening_float})
    assert response.status_code == 201, response.text
    return response.json()


def close_shift(client: TestClient, shift_id: int, counted_cash: int):
    return client.post(
        f'{SHIFTS}{shift_id}/close', json={'counted_cash': counted_cash}
    )


RECEIPTS = '/api/v1/receipts/'


def method_id(client: TestClient, name: str = 'Tunai') -> int:
    methods = client.get('/api/v1/payment-methods/').json()
    return next(method['id'] for method in methods if method['name'] == name)


def cart(*items: tuple[Sku, float]) -> list[dict]:
    return [
        {'sku_id': sku.id, 'quantity': quantity} for sku, quantity in items
    ]


def sell(
    client: TestClient,
    *items: tuple[Sku, float],
    payments: list[dict] | None = None,
):
    """Sell `items` at today's prices, paid in exact cash unless
    `payments` says otherwise."""
    lines = cart(*items)
    total = client.post(f'{RECEIPTS}quote', json={'lines': lines}).json()[
        'total'
    ]
    if payments is None:
        payments = [{'payment_method_id': method_id(client), 'amount': total}]
    return client.post(
        RECEIPTS,
        json={'lines': lines, 'payments': payments, 'expected_total': total},
    )


def give_back(
    client: TestClient,
    receipt: dict,
    returns: list[tuple[int, float, str]],
    *,
    new: tuple[tuple[Sku, float], ...] = (),
    payments: list[dict] | None = None,
    refund_method_id: int | None = None,
):
    """Bring back (line index, quantity, condition) from `receipt`, and
    take `new` instead."""
    body = {
        'original_receipt_id': receipt['id'],
        'returns': [
            {
                'original_line_id': receipt['lines'][index]['id'],
                'quantity': quantity,
                'condition': condition,
            }
            for index, quantity, condition in returns
        ],
        'lines': cart(*new),
    }
    quoted = client.post(f'{RECEIPTS}quote', json=body)
    if quoted.status_code != 200:
        return quoted
    total = quoted.json()['total']
    if payments is None and total > 0:
        payments = [{'payment_method_id': method_id(client), 'amount': total}]
    return client.post(
        RECEIPTS,
        json={
            **body,
            'payments': payments or [],
            'refund_method_id': refund_method_id,
            'expected_total': total,
        },
    )


PROMOTIONS = '/api/v1/promotions/'
NOW = datetime.now(UTC)


def promote(
    client: TestClient,
    target_kind: str,
    target_ids: list[int | None],
    *,
    value: int,
    discount_kind: str = 'percentage',
    starts: timedelta = timedelta(hours=-1),
    ends: timedelta = timedelta(days=1),
    name: str = 'Promo',
) -> dict:
    response = client.post(
        PROMOTIONS,
        json={
            'name': name,
            'discount_kind': discount_kind,
            'value': value,
            'target_kind': target_kind,
            'target_ids': target_ids,
            'starts_at': (NOW + starts).isoformat(),
            'ends_at': (NOW + ends).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def posted(
    session: Session,
    document_type: str,
    document_id: int,
    event: str | None = None,
) -> dict[str, Decimal]:
    """What a document posted, per account name: a debit above zero, a
    credit below."""
    from sqlmodel import col, select

    from opname360.models import Account, JournalEntry, JournalLine

    query = (
        select(Account.name, JournalLine.debit, JournalLine.credit)
        .join(JournalLine, col(JournalLine.account_id) == Account.id)
        .join(JournalEntry, col(JournalLine.entry_id) == JournalEntry.id)
        .where(
            JournalEntry.document_type == document_type,
            JournalEntry.document_id == document_id,
        )
    )
    if event is not None:
        query = query.where(JournalEntry.event == event)
    totals: dict[str, Decimal] = {}
    for name, debit, credit in session.exec(query).all():
        totals[name] = totals.get(name, Decimal(0)) + debit - credit
    return {name: amount for name, amount in totals.items() if amount}


def account_balance(session: Session, name: str) -> Decimal:
    """Debit minus credit of the account called `name`, over all time."""
    from sqlmodel import func, select

    from opname360.models import Account, JournalLine

    total = session.exec(
        select(func.sum(JournalLine.debit - JournalLine.credit))
        .join(Account, JournalLine.account_id == Account.id)
        .where(Account.name == name)
    ).one()
    return total or Decimal(0)


def stock_value(session: Session) -> Decimal:
    """The total Stock Value, as in the Stok screen."""
    from sqlmodel import func, select

    from opname360.models import StockBalance

    return session.exec(select(func.sum(StockBalance.value))).one() or Decimal(
        0
    )
