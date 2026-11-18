"""Slice 6, rules 9-12: the till sells medicine by Batch, the one that
expires first first, and never what may be expired."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import (
    RECEIPTS,
    batch_line,
    cart,
    expiry,
    give_back,
    new_medicine,
    new_receipt,
    new_supplier,
    open_shift,
    sell,
    stock_of,
)
from .test_batches import batches_of
from .test_void_and_close import void

from opname360.models import Batch, Sku
from opname360.services.documents import shop_now


def stocked(
    client: TestClient, session: Session, *batches: tuple[str, int, int]
) -> Sku:
    """A medicine with (number, quantity, days to expiry) Batches."""
    pills = new_medicine(client, session)
    supplier = new_supplier(client, f'PT Herbal {pills.id}')
    new_receipt(
        client,
        supplier['id'],
        [
            batch_line(pills.id, quantity, 20000, number, expiry(days))
            for number, quantity, days in batches
        ],
    )
    return pills


def expire(session: Session, sku: Sku, number: str) -> None:
    """Pretend the Batch expired yesterday."""
    batch = session.exec(
        select(Batch).where(Batch.sku_id == sku.id, Batch.number == number)
    ).one()
    batch.expires_on = shop_now().date() - timedelta(days=1)
    session.add(batch)
    session.flush()


def test_a_sale_takes_the_batch_that_expires_first(
    owner_client: TestClient, session: Session
) -> None:
    pills = stocked(owner_client, session, ('LATE', 5, 300), ('SOON', 5, 100))
    open_shift(owner_client)
    response = sell(owner_client, (pills, 7))
    assert response.status_code == 201, response.text
    assert batches_of(owner_client, pills) == {'SOON': 0, 'LATE': 3}
    assert stock_of(owner_client, pills.id) == (3, 60000)

    # Beyond what is held, the first one to expire goes negative.
    assert sell(owner_client, (pills, 5)).status_code == 201
    assert batches_of(owner_client, pills) == {'SOON': -2, 'LATE': 0}


def test_expired_stock_is_never_sold_by_accident(
    owner_client: TestClient, session: Session
) -> None:
    pills = stocked(owner_client, session, ('OLD', 3, 10), ('NEW', 4, 300))
    expire(session, pills, 'OLD')
    open_shift(owner_client)
    assert sell(owner_client, (pills, 2)).status_code == 201
    assert batches_of(owner_client, pills) == {'OLD': 3, 'NEW': 2}

    # Only 2 unexpired left: the third unit in hand may be an expired one.
    quoted = owner_client.post(
        f'{RECEIPTS}quote', json={'lines': cart((pills, 3))}
    )
    assert quoted.status_code == 409
    assert quoted.json()['detail'] == (
        f'{pills.product.name}: yang belum kedaluwarsa tinggal 2 botol; '
        'sisanya batch OLD yang sudah kedaluwarsa. Jangan dijual; serahkan '
        'ke Admin.'
    )
    assert sell(owner_client, (pills, 2)).status_code == 201

    expire(session, pills, 'NEW')
    refused = owner_client.post(
        f'{RECEIPTS}quote', json={'lines': cart((pills, 1))}
    )
    assert refused.status_code == 409
    assert 'semua batch sudah kedaluwarsa' in refused.json()['detail']


def test_a_medicine_without_a_batch_is_not_sold(
    owner_client: TestClient, session: Session
) -> None:
    pills = new_medicine(owner_client, session)
    open_shift(owner_client)
    response = owner_client.post(
        f'{RECEIPTS}quote', json={'lines': cart((pills, 1))}
    )
    assert response.status_code == 409
    assert 'belum punya batch' in response.json()['detail']


def test_returns_and_voids_put_units_back_in_their_batch(
    owner_client: TestClient, session: Session
) -> None:
    pills = stocked(owner_client, session, ('LATE', 5, 300), ('SOON', 2, 100))
    open_shift(owner_client)
    sale = sell(owner_client, (pills, 4)).json()
    assert batches_of(owner_client, pills) == {'SOON': 0, 'LATE': 3}

    response = give_back(owner_client, sale, [(0, 1, 'resellable')])
    assert response.status_code == 201, response.text
    assert batches_of(owner_client, pills) == {'SOON': 1, 'LATE': 3}
    response = give_back(owner_client, sale, [(0, 1, 'damaged')])
    assert response.status_code == 201, response.text
    assert batches_of(owner_client, pills) == {'SOON': 1, 'LATE': 3}

    other = sell(owner_client, (pills, 3)).json()
    assert batches_of(owner_client, pills) == {'SOON': 0, 'LATE': 1}
    assert void(owner_client, other).status_code == 200
    assert batches_of(owner_client, pills) == {'SOON': 1, 'LATE': 3}
