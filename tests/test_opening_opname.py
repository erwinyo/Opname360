"""Slice 2, rules 18-20: the Opening Opname."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import (
    OPNAMES,
    count,
    lines_of,
    make_user,
    new_sku,
    open_opname,
    receive,
    stock_of,
    switch_to,
)

from opname360.models import CostLayer, Role, Sku, StockMovement, User


def counted_opening(
    client: TestClient,
    session: Session,
    owner: User,
    counts: dict[int | None, float],
) -> dict:
    """An Opening Opname with `counts`, everything else confirmed zero,
    closed for Review."""
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(client, [checker], is_opening=True)
    switch_to(client, checker)
    for sku_id, quantity in counts.items():
        count(client, opname['id'], sku_id=sku_id, quantity=quantity)
    switch_to(client, owner)
    rest = [
        line['id'] for line in lines_of(client, opname['id'], show='uncounted')
    ]
    if rest:
        client.post(
            f'{OPNAMES}{opname["id"]}/confirm-zero', json={'line_ids': rest}
        )
    response = client.post(f'{OPNAMES}{opname["id"]}/close-counting')
    assert response.status_code == 200, response.text
    return response.json()


def with_import_cost(session: Session, sku: Sku, cost: int) -> None:
    """As if the catalogue import filled in "last purchase cost"."""
    sku.latest_unit_cost = Decimal(cost)
    session.add(sku)
    session.commit()


# Rule 18


def test_the_opening_opname_counts_everything_before_any_movement(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    other = new_sku(owner_client, session)
    checker = make_user(session, 'budi', Role.cashier)

    # Asking for one SKU still counts all of them.
    opname = open_opname(
        owner_client,
        [checker],
        is_opening=True,
        scope='skus',
        sku_ids=[sku.id],
    )
    assert opname['is_opening'] is True
    assert opname['scope'] == 'everything'
    assert {
        line['sku_id'] for line in lines_of(owner_client, opname['id'])
    } == {
        sku.id,
        other.id,
    }
    owner_client.post(f'{OPNAMES}{opname["id"]}/cancel')

    receive(owner_client, sku, 1, 1000)
    response = owner_client.post(
        OPNAMES, json={'checker_ids': [checker.id], 'is_opening': True}
    )
    assert response.status_code == 409
    assert 'sebelum ada mutasi stok' in response.json()['detail']


# Rule 19


def test_every_counted_line_needs_an_opening_cost_from_the_import(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    imported = new_sku(owner_client, session)
    with_import_cost(session, imported, 4500)
    unknown = new_sku(owner_client, session)
    opname = counted_opening(
        owner_client, session, owner, {imported.id: 3, unknown.id: 2}
    )

    lines = {
        line['sku_id']: line for line in lines_of(owner_client, opname['id'])
    }
    assert Decimal(lines[imported.id]['entered_unit_cost']) == 4500
    assert Decimal(lines[imported.id]['variance_value']) == 13500
    assert lines[unknown.id]['needs_cost'] is True
    response = owner_client.post(f'{OPNAMES}{opname["id"]}/approve')
    assert response.status_code == 409
    assert 'isi harga per pcs' in response.json()['detail']

    response = owner_client.put(
        f'{OPNAMES}{opname["id"]}/lines/{lines[unknown.id]["id"]}',
        json={'unit_cost': 7000},
    )
    assert response.status_code == 200, response.text
    response = owner_client.post(f'{OPNAMES}{opname["id"]}/approve')
    assert response.status_code == 200, response.text
    assert stock_of(owner_client, imported.id) == (3, 13500)
    assert stock_of(owner_client, unknown.id) == (2, 14000)
    session.refresh(unknown)
    assert unknown.latest_unit_cost == 7000


# Rule 20


def test_approval_writes_opening_stock_and_fifo_cost_layers(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    shirt = new_sku(owner_client, session)
    hat = new_sku(owner_client, session, 'fifo')
    gone = new_sku(owner_client, session)
    for sku, cost in ((shirt, 5000), (hat, 8000), (gone, 1000)):
        with_import_cost(session, sku, cost)
    opname = counted_opening(
        owner_client, session, owner, {shirt.id: 10, hat.id: 4}
    )
    # Opening stock is not a Surplus: no reasons, no resolutions.
    response = owner_client.post(f'{OPNAMES}{opname["id"]}/approve')
    assert response.status_code == 200, response.text
    assert response.json()['surplus_count'] == 2
    assert Decimal(response.json()['surplus_value']) == 82000

    movements = session.exec(
        select(StockMovement)
        .where(StockMovement.document_id == opname['id'])
        .order_by(col(StockMovement.sku_id))
    ).all()
    assert [(m.sku_id, m.reason, m.quantity, m.value) for m in movements] == [
        (shirt.id, 'opening', 10, 50000),
        (hat.id, 'opening', 4, 32000),
    ]
    [layer] = session.exec(
        select(CostLayer).where(CostLayer.sku_id == hat.id)
    ).all()
    assert (layer.quantity_remaining, layer.unit_cost) == (4, 8000)
    # Found nothing of the third SKU: no movement, nothing in stock.
    assert stock_of(owner_client, gone.id) == (0, 0)


def test_the_screen_is_told_whether_an_opening_opname_is_still_possible(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    assert owner_client.get(f'{OPNAMES}opening-allowed').json() is True
    receive(owner_client, sku, 1, 1000)
    assert owner_client.get(f'{OPNAMES}opening-allowed').json() is False
