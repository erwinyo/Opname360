"""Slice 6, rules 1-5: the Owner switches a Category's Costing Method."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_user, new_sku, switch_to
from .test_costing import issue, layers, on_hand, receive

from opname360.models import Role, Sku


def switch(client: TestClient, sku: Sku, method: str):
    category_id = sku.product.sub_category.category_id
    return client.post(
        f'/api/v1/categories/{category_id}/costing-method',
        json={'costing_method': method},
    )


def test_moving_average_to_fifo_starts_from_one_layer(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'moving_average')
    receive(session, sku, 10, 1000)
    receive(session, sku, 10, 2000)

    response = switch(owner_client, sku, 'fifo')
    assert response.status_code == 200, response.text
    assert response.json()['costing_method'] == 'fifo'
    assert on_hand(session, sku) == (20, 30000)
    assert layers(session, sku) == [(20, 1500)]

    receive(session, sku, 10, 3000)
    assert issue(session, sku, 25) == 20 * 1500 + 5 * 3000
    assert on_hand(session, sku) == (5, 15000)


def test_fifo_to_moving_average_averages_what_is_left(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'fifo')
    receive(session, sku, 10, 1000)
    receive(session, sku, 10, 2000)
    assert issue(session, sku, 5) == 5000

    assert switch(owner_client, sku, 'moving_average').status_code == 200
    assert on_hand(session, sku) == (15, 25000)
    assert layers(session, sku) == []
    # 25.000 / 15 a unit, no longer the oldest delivery first.
    assert issue(session, sku, 3) == 5000


def test_only_the_owner_switches_and_it_is_logged(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'moving_average')
    receive(session, sku, 3, 1001)
    assert switch(owner_client, sku, 'moving_average').status_code == 409

    switch_to(owner_client, make_user(session, 'admin-hpp', Role.admin))
    assert switch(owner_client, sku, 'fifo').status_code == 403
    category_id = sku.product.sub_category.category_id
    edited = owner_client.patch(
        f'/api/v1/categories/{category_id}',
        json={'name': 'Obat', 'costing_method': 'fifo'},
    ).json()
    assert edited['costing_method'] == 'moving_average'

    switch_to(owner_client, make_user(session, 'pemilik-2', Role.owner))
    assert switch(owner_client, sku, 'fifo').status_code == 200
    entry = owner_client.get('/api/v1/activity-log/').json()['items'][0]
    assert entry['action'] == 'category.switch_costing_method'
    assert entry['summary'] == (
        'Mengganti metode HPP Obat dari Rata-rata ke FIFO; nilai stok saat '
        'itu Rp 3.003.'
    )
    assert on_hand(session, sku) == (3, Decimal(3003))
