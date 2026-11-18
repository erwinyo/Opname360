"""Slice 6, rules 6-8: Batches come in on Goods Receipts and leave on
Supplier Returns and Reversals."""

from itertools import count

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import (
    batch_line,
    expiry,
    new_category,
    new_medicine,
    new_product,
    new_receipt,
    new_sku,
    new_supplier,
    receipt_line,
    sku_row,
)
from .test_supplier_returns import new_return

from opname360.models import Sku


GOODS = '/api/v1/goods-receipts/'
_suppliers = count(1)


def herbal(client: TestClient) -> dict:
    return new_supplier(client, f'PT Herbal {next(_suppliers)}')


def card(client: TestClient, sku: Sku) -> dict:
    return client.get(f'/api/v1/stock/skus/{sku.id}/card').json()


def batches_of(client: TestClient, sku: Sku) -> dict[str, float]:
    return {
        batch['number']: float(batch['quantity'])
        for batch in card(client, sku)['batches']
    }


def draft(client: TestClient, lines: list[dict]) -> dict:
    supplier = herbal(client)
    return new_receipt(client, supplier['id'], lines, complete=False)


def test_a_medicine_line_needs_a_batch_and_expiry(
    owner_client: TestClient, session: Session
) -> None:
    pills = new_medicine(owner_client, session)
    receipt = draft(owner_client, [receipt_line(pills.id, 10, 20000)])
    assert receipt['lines'][0]['tracks_batches'] is True
    response = owner_client.post(f'{GOODS}{receipt["id"]}/complete')
    assert response.status_code == 409
    assert 'nomor batch' in response.json()['detail']

    receipt = draft(
        owner_client,
        [batch_line(pills.id, 10, 20000, ' b-01 ', expiry(200))],
    )
    assert receipt['lines'][0]['batch_number'] == 'B-01'
    response = owner_client.post(f'{GOODS}{receipt["id"]}/complete')
    assert response.status_code == 200, response.text
    assert batches_of(owner_client, pills) == {'B-01': 10}
    [movement] = card(owner_client, pills)['items']
    assert movement['batch_number'] == 'B-01'


def test_a_batch_keeps_its_expiry_and_an_expired_one_stays_out(
    owner_client: TestClient, session: Session
) -> None:
    pills = new_medicine(owner_client, session)
    supplier = herbal(owner_client)
    new_receipt(
        owner_client,
        supplier['id'],
        [
            batch_line(pills.id, 4, 20000, 'B-01', expiry(200)),
            batch_line(pills.id, 6, 21000, 'B-02', expiry(300)),
        ],
    )
    new_receipt(
        owner_client,
        supplier['id'],
        [batch_line(pills.id, 5, 20000, 'B-01', expiry(200))],
    )
    assert batches_of(owner_client, pills) == {'B-01': 9, 'B-02': 6}

    for line in (
        batch_line(pills.id, 1, 20000, 'B-01', expiry(201)),
        batch_line(pills.id, 1, 20000, 'B-03', expiry(-1)),
    ):
        receipt = draft(owner_client, [line])
        response = owner_client.post(f'{GOODS}{receipt["id"]}/complete')
        assert response.status_code == 409
    assert 'kedaluwarsa' in response.json()['detail']
    # Expiring today is still fine.
    receipt = draft(
        owner_client, [batch_line(pills.id, 1, 20000, 'B-04', expiry(0))]
    )
    assert (
        owner_client.post(f'{GOODS}{receipt["id"]}/complete').status_code
        == 200
    )


def test_other_skus_ignore_batches(
    owner_client: TestClient, session: Session
) -> None:
    shirt = new_sku(owner_client, session)
    receipt = draft(
        owner_client, [batch_line(shirt.id, 3, 50000, 'X', expiry(9))]
    )
    assert receipt['lines'][0]['batch_number'] is None
    assert (
        owner_client.post(f'{GOODS}{receipt["id"]}/complete').status_code
        == 200
    )
    assert card(owner_client, shirt)['batches'] == []


def test_medicine_is_not_produced(
    owner_client: TestClient, session: Session
) -> None:
    pills = new_medicine(owner_client, session)
    response = owner_client.post(
        '/api/v1/production-receipts/',
        json={
            'produced_on': expiry(0),
            'lines': [{'sku_id': pills.id, 'quantity': 1, 'unit_cost': 1}],
        },
    )
    assert response.status_code == 409
    assert 'Barang Masuk' in response.json()['detail']


def test_returns_and_reversals_leave_from_the_same_batch(
    owner_client: TestClient, session: Session
) -> None:
    pills = new_medicine(owner_client, session)
    supplier = herbal(owner_client)
    first = new_receipt(
        owner_client,
        supplier['id'],
        [batch_line(pills.id, 10, 20000, 'B-01', expiry(300))],
    )
    second = new_receipt(
        owner_client,
        supplier['id'],
        [batch_line(pills.id, 8, 20000, 'B-02', expiry(100))],
    )
    response = new_return(owner_client, first, [3])
    assert response.status_code == 200, response.text
    assert batches_of(owner_client, pills) == {'B-02': 8, 'B-01': 7}

    response = owner_client.post(
        f'{GOODS}{second["id"]}/reverse', json={'reason': 'Salah input'}
    )
    assert response.status_code == 200, response.text
    assert batches_of(owner_client, pills) == {'B-02': 0, 'B-01': 7}


def test_tracking_batches_is_fixed_once_stock_has_moved(
    owner_client: TestClient, session: Session
) -> None:
    category = new_category(owner_client, 'Obat China', ('Pil',))
    assert category['tracks_batches'] is False
    url = f'/api/v1/categories/{category["id"]}'
    changed = owner_client.patch(url, json={'tracks_batches': True}).json()
    assert changed['tracks_batches'] is True
    product = new_product(
        owner_client, category['sub_categories'][0]['id'], 'Pil Angin'
    )
    pills = session.get(Sku, product['skus'][0]['id'])
    supplier = herbal(owner_client)
    assert pills is not None
    new_receipt(
        owner_client,
        supplier['id'],
        [batch_line(pills.id, 1, 1000, 'B-01', expiry(30))],
    )
    response = owner_client.patch(url, json={'tracks_batches': False})
    assert response.status_code == 409
    assert 'sudah bergerak' in response.json()['detail']


def test_finding_a_sku_says_whether_it_tracks_batches(
    owner_client: TestClient, session: Session
) -> None:
    pills = new_medicine(owner_client, session)
    shirt = new_sku(owner_client, session, **sku_row(size='12'))
    found = {
        option['id']: option['tracks_batches']
        for code in (pills.code, shirt.code)
        for option in owner_client.get(
            '/api/v1/products/skus/search', params={'query': code}
        ).json()
    }
    assert found == {pills.id: True, shirt.id: False}
