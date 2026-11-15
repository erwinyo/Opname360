from decimal import Decimal

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import (
    new_receipt,
    new_sku,
    new_supplier,
    receipt_line,
    stock_of,
)


RETURNS = '/api/v1/supplier-returns/'


@pytest.fixture
def received(owner_client: TestClient, session: Session) -> dict:
    """A completed Goods Receipt of 10 at Rp 5.000 and 4 at Rp 9.000."""
    shirt = new_sku(owner_client, session)
    pen = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    return new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 10, 5000), receipt_line(pen.id, 4, 9000)],
    )


def new_return(
    client: TestClient,
    receipt: dict,
    quantities: list[float],
    *,
    complete: bool = True,
):
    response = client.post(
        RETURNS,
        json={
            'goods_receipt_id': receipt['id'],
            'returned_on': '2026-11-16',
            'note': 'Jahitan rusak',
            'lines': [
                {'goods_receipt_line_id': line['id'], 'quantity': quantity}
                for line, quantity in zip(
                    receipt['lines'], quantities, strict=False
                )
                if quantity
            ],
        },
    )
    if response.status_code != 201 or not complete:
        return response
    return client.post(f'{RETURNS}{response.json()["id"]}/complete')


def test_returned_goods_leave_stock_and_are_refunded_at_receipt_cost(
    owner_client: TestClient, received: dict
) -> None:
    shirt = received['lines'][0]

    response = new_return(owner_client, received, [3])

    assert response.status_code == 200, response.text
    completed = response.json()
    assert completed['number'].startswith('RB-')
    assert completed['goods_receipt_number'] == received['number']
    assert completed['supplier_name'] == 'CV Sumber Jaya'
    assert Decimal(completed['total_refund']) == 15000
    assert Decimal(completed['lines'][0]['stock_cost']) == 15000
    assert stock_of(owner_client, shirt['sku_id']) == (7, 35000)


def test_cannot_return_more_than_was_received_minus_earlier_returns(
    owner_client: TestClient, received: dict
) -> None:
    assert new_return(owner_client, received, [11]).status_code == 409
    assert new_return(owner_client, received, [6]).status_code == 200

    too_many = new_return(owner_client, received, [5])

    assert too_many.status_code == 409
    assert 'paling banyak 4 pcs' in too_many.json()['detail']
    assert new_return(owner_client, received, [4]).status_code == 200
    receipt = owner_client.get(
        f'/api/v1/goods-receipts/{received["id"]}'
    ).json()
    assert Decimal(receipt['lines'][0]['returned_quantity']) == 10


def test_two_drafts_cannot_together_return_more_than_was_received(
    owner_client: TestClient, received: dict
) -> None:
    first = new_return(owner_client, received, [7], complete=False).json()
    second = new_return(owner_client, received, [7], complete=False).json()

    assert (
        owner_client.post(f'{RETURNS}{first["id"]}/complete').status_code
        == 200
    )
    assert (
        owner_client.post(f'{RETURNS}{second["id"]}/complete').status_code
        == 409
    )


def test_only_a_completed_receipt_can_be_returned_from(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    draft = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(sku.id, 5, 100)],
        complete=False,
    )

    assert new_return(owner_client, draft, [1]).status_code == 409


def test_a_line_must_belong_to_the_receipt(
    owner_client: TestClient, session: Session, received: dict
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client, 'PT Lain')
    other = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 5, 100)]
    )

    response = owner_client.post(
        RETURNS,
        json={
            'goods_receipt_id': received['id'],
            'returned_on': '2026-11-16',
            'lines': [
                {
                    'goods_receipt_line_id': other['lines'][0]['id'],
                    'quantity': 1,
                }
            ],
        },
    )

    assert response.status_code == 404


def test_returned_goods_already_sold_leave_the_sku_in_negative_stock(
    owner_client: TestClient, received: dict
) -> None:
    """The return isn't blocked; the shortfall is flagged instead."""
    shirt = received['lines'][0]
    new_return(owner_client, received, [6])
    new_return(owner_client, received, [4])

    assert stock_of(owner_client, shirt['sku_id']) == (0, 0)
