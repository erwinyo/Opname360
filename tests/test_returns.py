"""Slice 3, rules 12-16 and 19: Customer Returns and Exchanges."""

from datetime import timedelta
from decimal import Decimal

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import (
    PROMOTIONS,
    RECEIPTS,
    SHIFTS,
    give_back,
    method_id,
    new_category,
    new_product,
    open_shift,
    receive,
    sell,
    sku_row,
    stock_of,
)

from opname360.models import MovementReason, Receipt, Sku, StockMovement


@pytest.fixture
def shirts(owner_client: TestClient, session: Session) -> dict[str, Sku]:
    """Sizes S (Rp 60.000) and M (Rp 65.000), 10 each at Rp 40.000."""
    category = new_category(owner_client, 'Seragam', ('Kaos',))
    product = new_product(
        owner_client,
        category['sub_categories'][0]['id'],
        'Kaos Olahraga',
        [
            sku_row(size='S', selling_price=60000),
            sku_row(size='M', selling_price=65000),
        ],
    )
    skus = {}
    for row in product['skus']:
        sku = session.get(Sku, row['id'])
        assert sku is not None
        receive(owner_client, sku, 10, 40000)
        skus[row['size']] = sku
    open_shift(owner_client, 100000)
    return skus


def movements_of(session: Session, receipt: dict) -> list[tuple]:
    return [
        (m.sku_id, m.reason, m.quantity, m.value)
        for m in session.exec(
            select(StockMovement)
            .where(StockMovement.document_number == receipt['number'])
            .order_by(col(StockMovement.id))
        ).all()
    ]


# Rule 12


def test_only_what_the_receipt_sold_can_come_back(
    owner_client: TestClient, shirts: dict[str, Sku]
) -> None:
    sale = sell(owner_client, (shirts['S'], 2)).json()
    other = sell(owner_client, (shirts['M'], 1)).json()

    found = owner_client.get(
        f'{RECEIPTS}for-return', params={'number': sale['number'].lower()}
    )
    assert found.json()['id'] == sale['id']
    response = give_back(owner_client, sale, [(0, 1, 'resellable')])
    assert response.status_code == 201, response.text
    returned = response.json()
    assert returned['number'].startswith('RJ-')
    assert returned['original_receipt_number'] == sale['number']

    response = give_back(owner_client, sale, [(0, 2, 'resellable')])
    assert response.status_code == 409
    assert 'paling banyak 1 pcs' in response.json()['detail']
    again = owner_client.get(f'{RECEIPTS}{sale["id"]}').json()
    assert Decimal(again['lines'][0]['returned_quantity']) == 1

    # A line of another Receipt is not on this one.
    response = owner_client.post(
        f'{RECEIPTS}quote',
        json={
            'original_receipt_id': sale['id'],
            'returns': [
                {
                    'original_line_id': other['lines'][0]['id'],
                    'quantity': 1,
                    'condition': 'resellable',
                }
            ],
        },
    )
    assert response.status_code == 404
    # Nor can a return itself be returned.
    response = owner_client.get(
        f'{RECEIPTS}for-return', params={'number': returned['number']}
    )
    assert response.status_code == 409


# Rules 13 and 19


def test_the_return_window_is_counted_on_the_day_of_the_return(
    owner_client: TestClient, session: Session, shirts: dict[str, Sku]
) -> None:
    sale = sell(owner_client, (shirts['S'], 1)).json()
    receipt = session.get(Receipt, sale['id'])
    assert receipt is not None
    receipt.created_at -= timedelta(days=10)
    session.add(receipt)
    session.commit()

    response = give_back(owner_client, sale, [(0, 1, 'resellable')])
    assert response.status_code == 409
    assert 'lewat batas retur 7 hari' in response.json()['detail']

    settings = owner_client.get('/api/v1/shop-settings/').json()
    owner_client.put(
        '/api/v1/shop-settings/', json={**settings, 'return_window_days': 10}
    )
    response = give_back(owner_client, sale, [(0, 1, 'resellable')])
    assert response.status_code == 201, response.text


# Rule 14


def test_the_refund_is_what_was_paid_after_discount_in_cash(
    owner_client: TestClient, session: Session, shirts: dict[str, Sku]
) -> None:
    small = shirts['S']
    small.selling_price = 33333
    session.add(small)
    session.commit()
    owner_client.post(
        PROMOTIONS,
        json={
            'name': 'Diskon 10%',
            'discount_kind': 'percentage',
            'value': 10,
            'target_kind': 'skus',
            'target_ids': [small.id],
            'starts_at': '2020-01-01T00:00:00Z',
            'ends_at': '2099-01-01T00:00:00Z',
        },
    )
    sale = sell(owner_client, (small, 3)).json()
    assert sale['total'] == 89999

    refunds = []
    for _ in range(3):
        response = give_back(owner_client, sale, [(0, 1, 'resellable')])
        assert response.status_code == 201, response.text
        refunds.append(response.json())
    assert [-r['total'] for r in refunds] == [30000, 29999, 30000]
    assert [p['method_name'] for p in refunds[0]['payments']] == ['Tunai']
    assert refunds[0]['payments'][0]['amount'] == -30000

    # Another method when the Cashier picks it.
    second = sell(owner_client, (shirts['M'], 1)).json()
    transfer = method_id(owner_client, 'Transfer Bank')
    response = give_back(
        owner_client, second, [(0, 1, 'resellable')], refund_method_id=transfer
    )
    assert response.json()['payments'][0]['method_name'] == 'Transfer Bank'

    shift = owner_client.get(f'{SHIFTS}current').json()
    expected = owner_client.get(f'{SHIFTS}{shift["id"]}').json()
    # Float + 89.999 + 65.000 taken in cash - 89.999 given back in cash.
    assert expected['expected_cash'] == 100000 + 65000


# Rule 15


def test_returned_goods_come_back_at_the_cost_they_were_sold_at(
    owner_client: TestClient, session: Session, shirts: dict[str, Sku]
) -> None:
    small = shirts['S']
    sale = sell(owner_client, (small, 2)).json()
    # The average moves on: 8 at 40.000 plus 8 at 60.000.
    receive(owner_client, small, 8, 60000)

    resellable = give_back(owner_client, sale, [(0, 1, 'resellable')]).json()
    assert movements_of(session, resellable) == [
        (small.id, MovementReason.customer_return, 1, 40000),
    ]
    damaged = give_back(owner_client, sale, [(0, 1, 'damaged')]).json()
    assert movements_of(session, damaged) == [
        (small.id, MovementReason.customer_return, 1, 40000),
        (small.id, MovementReason.write_off, -1, -40000),
    ]
    assert stock_of(owner_client, small.id) == (17, 840000)
    assert damaged['lines'][0]['condition'] == 'damaged'


# Rule 16


def test_an_exchange_settles_only_the_difference(
    owner_client: TestClient, session: Session, shirts: dict[str, Sku]
) -> None:
    small, medium = shirts['S'], shirts['M']
    sale = sell(owner_client, (small, 2)).json()

    # Size S for size M: the customer adds Rp 5.000.
    up = give_back(
        owner_client, sale, [(0, 1, 'resellable')], new=((medium, 1),)
    )
    assert up.status_code == 201, up.text
    exchange = up.json()
    assert exchange['number'].startswith('TT-')
    assert (exchange['kind'], exchange['total']) == ('exchange', 5000)
    assert exchange['refund_total'] == 60000
    assert movements_of(session, exchange) == [
        (small.id, MovementReason.customer_return, 1, 40000),
        (medium.id, MovementReason.sale, -1, -40000),
    ]

    # An even swap needs no payment.
    even = give_back(
        owner_client, sale, [(0, 1, 'resellable')], new=((small, 1),)
    )
    assert (even.json()['total'], even.json()['payments']) == (0, [])

    # Cheaper goods: the difference goes back in cash only.
    sale = sell(owner_client, (medium, 1)).json()
    transfer = method_id(owner_client, 'Transfer Bank')
    down = give_back(
        owner_client,
        sale,
        [(0, 1, 'resellable')],
        new=((small, 1),),
        refund_method_id=transfer,
    )
    assert down.status_code == 409
    assert 'tunai' in down.json()['detail']
    down = give_back(
        owner_client, sale, [(0, 1, 'resellable')], new=((small, 1),)
    )
    assert down.json()['total'] == -5000
    assert down.json()['payments'][0]['method_name'] == 'Tunai'
