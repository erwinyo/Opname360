"""Slice 2, rules 9-11: closing counting, Review and Recount."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import (
    COUNTING,
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

from opname360.models import CountEntry, OpnameLine, Role, User


def close(client: TestClient, opname_id: int):
    return client.post(f'{OPNAMES}{opname_id}/close-counting')


# Rule 9


def test_counting_closes_only_when_every_line_is_counted_or_zero(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    counted = new_sku(owner_client, session)
    missing = new_sku(owner_client, session)
    receive(owner_client, missing, 2, 1000)
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(owner_client, [checker])
    switch_to(owner_client, checker)
    count(owner_client, opname['id'], sku_id=counted.id, quantity=1)

    switch_to(owner_client, owner)
    response = close(owner_client, opname['id'])
    assert response.status_code == 409
    assert '1 SKU yang belum dihitung' in response.json()['detail']

    [uncounted] = lines_of(owner_client, opname['id'], show='uncounted')
    response = owner_client.post(
        f'{OPNAMES}{opname["id"]}/confirm-zero',
        json={'line_ids': [uncounted['id']]},
    )
    assert response.status_code == 200, response.text
    assert response.json()['counted_count'] == 2

    response = close(owner_client, opname['id'])
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'review'
    assert response.json()['counting_closed_by_name'] == 'Owner'
    # Confirming zero snapshots the System Quantity like a count does.
    line = {
        line['sku_id']: line for line in lines_of(owner_client, opname['id'])
    }
    assert Decimal(line[missing.id]['system_quantity']) == 2
    assert Decimal(line[missing.id]['physical_quantity']) == 0
    assert Decimal(line[missing.id]['variance']) == -2

    # Counting is over: Checkers can no longer add to a line.
    switch_to(owner_client, checker)
    response = count(owner_client, opname['id'], sku_id=counted.id)
    assert response.status_code == 409
    sheet = owner_client.get(f'{COUNTING}{opname["id"]}').json()
    assert sheet['can_count'] is False


# Rule 10


def test_the_approver_is_an_owner_or_admin_who_did_not_count(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 5, 1000)
    admin_checker = make_user(session, 'budi', Role.admin)
    other_admin = make_user(session, 'sari', Role.admin)
    opname = open_opname(owner_client, [admin_checker, owner])
    switch_to(owner_client, admin_checker)
    count(owner_client, opname['id'], sku_id=sku.id, quantity=4)
    close(owner_client, opname['id'])
    [line] = lines_of(owner_client, opname['id'])
    recount_url = f'{OPNAMES}{opname["id"]}/lines/{line["id"]}/recount'

    # Neither Checker sees the Variance or may review, the Owner included.
    for checker in (admin_checker, owner):
        switch_to(owner_client, checker)
        detail = owner_client.get(f'{OPNAMES}{opname["id"]}').json()
        assert (detail['revealed'], detail['can_approve']) == (False, False)
        assert lines_of(owner_client, opname['id'])[0]['variance'] is None
        assert owner_client.post(recount_url).status_code == 403

    switch_to(owner_client, other_admin)
    detail = owner_client.get(f'{OPNAMES}{opname["id"]}').json()
    assert (detail['revealed'], detail['can_approve']) == (True, True)
    assert detail['shortage_count'] == 1
    assert Decimal(detail['shortage_value']) == 1000
    [line] = lines_of(owner_client, opname['id'], show='variance')
    assert Decimal(line['variance']) == -1
    assert Decimal(line['variance_value']) == -1000


# Rule 11


def test_recount_sends_one_line_back_while_the_rest_waits(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    recounted = new_sku(owner_client, session)
    waiting = new_sku(owner_client, session)
    receive(owner_client, recounted, 5, 1000)
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(owner_client, [checker])
    switch_to(owner_client, checker)
    count(owner_client, opname['id'], sku_id=recounted.id, quantity=2)
    count(owner_client, opname['id'], sku_id=waiting.id, quantity=1)
    switch_to(owner_client, owner)
    close(owner_client, opname['id'])
    line = next(
        line
        for line in lines_of(owner_client, opname['id'])
        if line['sku_id'] == recounted.id
    )

    response = owner_client.post(
        f'{OPNAMES}{opname["id"]}/lines/{line["id"]}/recount'
    )
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'review'
    assert response.json()['recount_count'] == 1

    # The entries are cancelled, not deleted, and the snapshot is gone.
    entries = session.exec(
        select(CountEntry).where(CountEntry.line_id == line['id'])
    ).all()
    assert len(entries) == 1
    session.refresh(entries[0])
    assert entries[0].cancelled_at is not None
    stored = session.get(OpnameLine, line['id'])
    assert stored is not None
    session.refresh(stored)
    assert (stored.system_quantity, stored.physical_quantity) == (None, 0)

    # More arrives before the recount: the new snapshot includes it.
    receive(owner_client, recounted, 1, 1000)
    switch_to(owner_client, checker)
    assert owner_client.get(f'{COUNTING}{opname["id"]}').json()['can_count']
    assert (
        count(owner_client, opname['id'], sku_id=waiting.id).status_code == 409
    )
    response = count(
        owner_client, opname['id'], sku_id=recounted.id, quantity=6
    )
    assert response.status_code == 201, response.text

    switch_to(owner_client, owner)
    [line] = [
        line
        for line in lines_of(owner_client, opname['id'], show='variance')
        if line['sku_id'] == recounted.id
    ]
    assert Decimal(line['system_quantity']) == 6
    assert Decimal(line['variance']) == 0
    assert line['recount'] is True


def test_cancelling_leaves_stock_as_it_was(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 5, 1000)
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(owner_client, [checker])
    switch_to(owner_client, checker)
    count(owner_client, opname['id'], sku_id=sku.id, quantity=1)
    switch_to(owner_client, owner)
    close(owner_client, opname['id'])

    response = owner_client.post(f'{OPNAMES}{opname["id"]}/cancel')
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'cancelled'
    assert stock_of(owner_client, sku.id) == (5, 5000)
    response = owner_client.post(f'{OPNAMES}{opname["id"]}/cancel')
    assert response.status_code == 409
