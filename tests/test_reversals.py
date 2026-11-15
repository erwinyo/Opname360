from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import (
    new_receipt,
    new_sku,
    new_supplier,
    receipt_line,
    stock_of,
)
from .test_supplier_returns import RETURNS, new_return

from opname360.models import (
    ActivityLog,
    CostLayer,
    MovementReason,
    Sku,
    StockMovement,
)
from opname360.services import costing


RECEIPTS = '/api/v1/goods-receipts/'


def reverse(client: TestClient, url: str, reason: str = 'Salah ketik harga'):
    return client.post(f'{url}/reverse', json={'reason': reason})


def test_reversing_a_receipt_takes_its_goods_back_out(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)]
    )

    response = reverse(owner_client, f'{RECEIPTS}{receipt["id"]}')

    assert response.status_code == 200, response.text
    reversed_receipt = response.json()
    assert reversed_receipt['status'] == 'reversed'
    reversal = reversed_receipt['reversal']
    assert reversal['number'].startswith('BTL-')
    assert reversal['reason'] == 'Salah ketik harga'
    assert reversal['created_by_name'] == 'Owner'
    assert stock_of(owner_client, sku.id) == (0, 0)
    newest = owner_client.get(f'/api/v1/stock/skus/{sku.id}/card').json()[
        'items'
    ][0]
    assert newest['reason'] == 'reversal'
    assert newest['document_number'] == reversal['number']
    # The Stock Card links the reversal to the receipt it cancels.
    assert newest['document_type'] == 'goods_receipt'
    assert newest['document_id'] == receipt['id']


def test_reversing_a_mistyped_cost_restores_the_average_exactly(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'moving_average')
    supplier = new_supplier(owner_client)
    new_receipt(owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)])
    typo = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 600000)]
    )

    reverse(owner_client, f'{RECEIPTS}{typo["id"]}')

    assert stock_of(owner_client, sku.id) == (10, 50000)


def test_reversing_under_fifo_takes_back_the_receipts_own_layer(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'fifo')
    supplier = new_supplier(owner_client)
    new_receipt(owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)])
    second = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 6000)]
    )

    reverse(owner_client, f'{RECEIPTS}{second["id"]}')

    assert stock_of(owner_client, sku.id) == (10, 50000)
    layers = session.exec(
        select(CostLayer).where(CostLayer.sku_id == sku.id)
    ).all()
    assert [
        (layer.quantity_remaining, layer.unit_cost) for layer in layers
    ] == [(10, 5000)]


def sell(session: Session, sku: Sku, quantity: int) -> None:
    """Stand-in for a POS sale until slice 3: goods out at their cost."""
    costing.issue(
        session,
        sku=sku,
        location_id=1,
        quantity=Decimal(quantity),
        reason=MovementReason.supplier_return,
        source=costing.Source('test', 1, 'TEST-1'),
        actor=None,
    )
    session.commit()


def test_reversing_goods_already_gone_leaves_negative_stock(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)]
    )
    sell(session, sku, 8)

    reverse(owner_client, f'{RECEIPTS}{receipt["id"]}')

    assert stock_of(owner_client, sku.id) == (-8, -40000)
    negative = owner_client.get(
        '/api/v1/stock/', params={'negative_only': True}
    ).json()
    assert [row['sku_id'] for row in negative['items']] == [sku.id]


def test_a_document_is_reversed_only_once_and_only_when_completed(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)]
    )
    draft = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(sku.id, 1, 1)],
        complete=False,
    )
    url = f'{RECEIPTS}{receipt["id"]}'

    assert reverse(owner_client, url).status_code == 200
    twice = reverse(owner_client, url)
    of_draft = reverse(owner_client, f'{RECEIPTS}{draft["id"]}')

    assert twice.status_code == 409
    assert 'sudah dibatalkan' in twice.json()['detail']
    assert of_draft.status_code == 409
    assert stock_of(owner_client, sku.id) == (0, 0)


def test_a_reversal_needs_a_reason(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 1, 1)]
    )
    url = f'{RECEIPTS}{receipt["id"]}'

    assert reverse(owner_client, url, '').status_code == 422
    assert reverse(owner_client, url, '   ').status_code == 409


def test_a_receipt_with_returns_is_reversed_only_after_its_returns(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)]
    )
    supplier_return = new_return(owner_client, receipt, [3]).json()
    receipt_url = f'{RECEIPTS}{receipt["id"]}'

    blocked = reverse(owner_client, receipt_url)

    assert blocked.status_code == 409
    assert supplier_return['number'] in blocked.json()['detail']
    assert (
        reverse(owner_client, f'{RETURNS}{supplier_return["id"]}').status_code
        == 200
    )
    assert stock_of(owner_client, sku.id) == (10, 50000)
    assert reverse(owner_client, receipt_url).status_code == 200
    assert stock_of(owner_client, sku.id) == (0, 0)


def test_goods_from_a_reversed_receipt_cannot_be_returned(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)]
    )
    draft = new_return(owner_client, receipt, [2], complete=False).json()
    reverse(owner_client, f'{RECEIPTS}{receipt["id"]}')

    response = owner_client.post(f'{RETURNS}{draft["id"]}/complete')

    assert response.status_code == 409
    assert 'sudah dibatalkan' in response.json()['detail']


def test_reversing_a_receipt_that_filled_negative_stock_restores_it(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    new_receipt(owner_client, supplier['id'], [receipt_line(sku.id, 3, 5000)])
    sell(session, sku, 5)
    assert stock_of(owner_client, sku.id) == (-2, -10000)
    filling = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 6000)]
    )
    assert stock_of(owner_client, sku.id) == (8, 48000)

    reverse(owner_client, f'{RECEIPTS}{filling["id"]}')

    assert stock_of(owner_client, sku.id) == (-2, -10000)


def test_every_movement_of_a_reversed_document_is_mirrored(
    owner_client: TestClient, session: Session
) -> None:
    shirt = new_sku(owner_client, session)
    pen = new_sku(owner_client, session, 'fifo')
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 10, 5000), receipt_line(pen.id, 7, 3000)],
    )

    reverse(owner_client, f'{RECEIPTS}{receipt["id"]}')

    movements = session.exec(
        select(StockMovement)
        .where(StockMovement.document_id == receipt['id'])
        .order_by(col(StockMovement.id))
    ).all()
    assert sum(m.quantity for m in movements) == 0
    assert sum(m.value for m in movements) == 0
    assert stock_of(owner_client, shirt.id) == (0, 0)
    assert stock_of(owner_client, pen.id) == (0, 0)


def test_reversals_are_written_to_the_activity_log(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 1, 1)]
    )

    reversal = reverse(owner_client, f'{RECEIPTS}{receipt["id"]}').json()[
        'reversal'
    ]

    logged = session.exec(
        select(ActivityLog).where(
            ActivityLog.action == 'goods_receipt.reverse'
        )
    ).one()
    assert logged.summary == (
        f'Membatalkan barang masuk {receipt["number"]} '
        f'({reversal["number"]}): Salah ketik harga'
    )


def test_reversing_a_supplier_return_puts_the_goods_back(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'fifo')
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 10, 5000)]
    )
    supplier_return = new_return(owner_client, receipt, [4]).json()
    assert stock_of(owner_client, sku.id) == (6, 30000)

    reverse(owner_client, f'{RETURNS}{supplier_return["id"]}')

    assert stock_of(owner_client, sku.id) == (10, 50000)
    receipt_now = owner_client.get(f'{RECEIPTS}{receipt["id"]}').json()
    assert Decimal(receipt_now['lines'][0]['returned_quantity']) == 0
