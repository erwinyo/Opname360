"""Slice 6, rules 13 and 14: a medicine is counted, reviewed and adjusted
per Batch, and expired stock is written off with a Partial Opname."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import (
    COUNTING,
    OPNAMES,
    RECEIPTS,
    cart,
    count,
    expiry,
    lines_of,
    make_user,
    new_medicine,
    new_sku,
    open_opname,
    open_shift,
    sell,
    switch_to,
)
from .test_batch_selling import expire, stocked
from .test_batches import batches_of
from .test_opname_approval import approve, resolve

from opname360.models import Role, User
from opname360.services.documents import shop_now


def by_batch(client: TestClient, opname: dict, sku_id: int | None) -> dict:
    return {
        line['batch_number']: line
        for line in lines_of(client, opname['id'])
        if line['sku_id'] == sku_id
    }


def close(client: TestClient, opname: dict, *, zero: list[dict]) -> None:
    if zero:
        response = client.post(
            f'{OPNAMES}{opname["id"]}/confirm-zero',
            json={'line_ids': [line['id'] for line in zero]},
        )
        assert response.status_code == 200, response.text
    response = client.post(f'{OPNAMES}{opname["id"]}/close-counting')
    assert response.status_code == 200, response.text


# Rule 13


def test_a_medicine_gets_a_line_per_batch_it_holds_or_owes(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    pills = stocked(
        owner_client, session, ('GONE', 2, 50), ('A', 5, 100), ('B', 3, 200)
    )
    open_shift(owner_client)
    # GONE expires first, so the sale empties it.
    assert sell(owner_client, (pills, 2)).status_code == 201
    unstocked = new_medicine(owner_client, session)
    shirt = new_sku(owner_client, session)
    checker = make_user(session, 'sari', Role.cashier)

    opname = open_opname(
        owner_client,
        [checker],
        scope='skus',
        sku_ids=[pills.id, unstocked.id, shirt.id],
    )

    lines = by_batch(owner_client, opname, pills.id)
    assert list(lines) == ['A', 'B']
    assert lines['A']['expires_on'] == expiry(100)
    assert list(by_batch(owner_client, opname, unstocked.id)) == [None]
    assert list(by_batch(owner_client, opname, shirt.id)) == [None]


def test_the_checker_picks_the_batch_or_types_a_new_one(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    pills = stocked(owner_client, session, ('A', 5, 100), ('B', 3, 200))
    checker = make_user(session, 'sari', Role.cashier)
    opname = open_opname(
        owner_client, [checker], scope='skus', sku_ids=[pills.id]
    )
    a = by_batch(owner_client, opname, pills.id)['A']

    switch_to(owner_client, checker)
    sheet = owner_client.get(f'{COUNTING}{opname["id"]}').json()
    [option] = sheet['batch_skus']
    assert option['id'] == pills.id
    assert [batch['number'] for batch in option['batches']] == ['A', 'B']
    # A medicine is found once by name, however many lines it has.
    found = owner_client.get(
        f'{COUNTING}{opname["id"]}/skus', params={'search': 'Pil'}
    ).json()
    assert [sku['id'] for sku in found] == [pills.id]

    response = count(owner_client, opname['id'], sku_id=pills.id)
    assert response.status_code == 409
    assert 'pilih batch' in response.json()['detail']
    response = count(
        owner_client,
        opname['id'],
        sku_id=pills.id,
        batch_id=option['batches'][0]['id'],
        quantity=5,
    )
    assert response.status_code == 201, response.text
    assert response.json()['batch_number'] == 'A'
    # A batch nobody recorded is found on the shelf: it gets its own line.
    response = count(
        owner_client,
        opname['id'],
        sku_id=pills.id,
        batch_number=' c-9 ',
        expires_on=expiry(400),
        quantity=2,
    )
    assert response.status_code == 201, response.text
    assert response.json()['batch_number'] == 'C-9'
    # A known number keeps its expiry date.
    response = count(
        owner_client,
        opname['id'],
        sku_id=pills.id,
        batch_number='A',
        expires_on=expiry(101),
    )
    assert response.status_code == 409

    switch_to(owner_client, owner)
    lines = by_batch(owner_client, opname, pills.id)
    assert list(lines) == ['A', 'B', 'C-9']
    close(owner_client, opname, zero=[lines['B']])
    lines = by_batch(owner_client, opname, pills.id)
    assert Decimal(lines['A']['variance']) == 0
    assert Decimal(lines['B']['variance']) == -3
    assert Decimal(lines['C-9']['variance']) == 2

    # A Recount sends back one Batch; the others wait.
    response = owner_client.post(
        f'{OPNAMES}{opname["id"]}/lines/{a["id"]}/recount'
    )
    assert response.status_code == 200, response.text
    switch_to(owner_client, checker)
    response = count(
        owner_client,
        opname['id'],
        sku_id=pills.id,
        batch_number='B',
        expires_on=expiry(200),
    )
    assert response.status_code == 409
    response = count(
        owner_client,
        opname['id'],
        sku_id=pills.id,
        batch_number='A',
        expires_on=expiry(100),
        quantity=4,
    )
    assert response.status_code == 201, response.text

    switch_to(owner_client, owner)
    lines = by_batch(owner_client, opname, pills.id)
    assert Decimal(lines['A']['variance']) == -1
    for number in ('A', 'B'):
        resolve(owner_client, opname, lines[number], shortage_reason='lost')
    response = approve(owner_client, opname)
    assert response.status_code == 200, response.text
    assert batches_of(owner_client, pills) == {'A': 4, 'B': 0, 'C-9': 2}


def test_a_line_without_a_batch_becomes_the_first_batch_counted(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    pills = new_medicine(owner_client, session)
    checker = make_user(session, 'sari', Role.cashier)
    opname = open_opname(
        owner_client, [checker], scope='skus', sku_ids=[pills.id]
    )
    [blank] = lines_of(owner_client, opname['id'])

    switch_to(owner_client, checker)
    for number, quantity in (('X', 4), ('Y', 1)):
        response = count(
            owner_client,
            opname['id'],
            sku_id=pills.id,
            batch_number=number,
            expires_on=expiry(300),
            quantity=quantity,
        )
        assert response.status_code == 201, response.text

    switch_to(owner_client, owner)
    lines = by_batch(owner_client, opname, pills.id)
    assert list(lines) == ['X', 'Y']
    assert lines['X']['id'] == blank['id']
    close(owner_client, opname, zero=[])
    for line in by_batch(owner_client, opname, pills.id).values():
        # Never bought, so the Surplus needs a cost.
        resolve(owner_client, opname, line, unit_cost=15000)
    response = approve(owner_client, opname)
    assert response.status_code == 200, response.text
    assert batches_of(owner_client, pills) == {'X': 4, 'Y': 1}

    # Now its expiry is known, the till sells it.
    open_shift(owner_client)
    assert sell(owner_client, (pills, 1)).status_code == 201


# Rule 14


def test_expired_stock_is_written_off_with_a_partial_opname(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    pills = stocked(owner_client, session, ('OLD', 3, 30), ('NEW', 5, 300))
    expire(session, pills, 'OLD')
    open_shift(owner_client)
    # 6 would need an expired unit, so the till refuses.
    quoted = owner_client.post(
        f'{RECEIPTS}quote', json={'lines': cart((pills, 6))}
    )
    assert quoted.status_code == 409

    # Taken off the shelf; the Partial Opname counts only the good Batch.
    checker = make_user(session, 'sari', Role.cashier)
    opname = open_opname(
        owner_client, [checker], scope='skus', sku_ids=[pills.id]
    )
    lines = by_batch(owner_client, opname, pills.id)
    switch_to(owner_client, checker)
    response = count(
        owner_client,
        opname['id'],
        sku_id=pills.id,
        batch_number='NEW',
        expires_on=expiry(300),
        quantity=5,
    )
    assert response.status_code == 201, response.text
    switch_to(owner_client, owner)
    close(owner_client, opname, zero=[lines['OLD']])
    old = by_batch(owner_client, opname, pills.id)['OLD']
    assert Decimal(old['variance']) == -3
    resolve(owner_client, opname, old, shortage_reason='expired')
    response = approve(owner_client, opname)
    assert response.status_code == 200, response.text
    assert batches_of(owner_client, pills) == {'OLD': 0, 'NEW': 5}

    today = str(shop_now().date())
    report = owner_client.get(
        '/api/v1/reports/variances',
        params={'start': today, 'end': today, 'group_by': 'reason'},
    ).json()
    [row] = report['rows']
    assert row['label'] == 'Kedaluwarsa'
    assert Decimal(row['shortage_quantity']) == 3
