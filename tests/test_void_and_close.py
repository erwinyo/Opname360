"""Slice 3, rules 3, 11 and 12: Void, the closing summary, and who bears
a short drawer."""

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import (
    RECEIPTS,
    SHIFTS,
    close_shift,
    make_user,
    method_id,
    new_sku,
    open_shift,
    receive,
    sell,
    stock_of,
    switch_to,
)

from opname360.models import MovementReason, Role, Sku, StockMovement, User


@pytest.fixture
def cashier(session: Session) -> User:
    return make_user(session, 'ani', Role.cashier)


@pytest.fixture
def shirt(owner_client: TestClient, session: Session) -> Sku:
    """Rp 80.000, 10 in stock at Rp 50.000."""
    sku = new_sku(owner_client, session, selling_price=80000)
    receive(owner_client, sku, 10, 50000)
    return sku


def void(client: TestClient, receipt: dict, reason: str = 'Salah input'):
    return client.post(
        f'{RECEIPTS}{receipt["id"]}/void', json={'reason': reason}
    )


def give_back(client: TestClient, receipt: dict, quantity: float = 1):
    body = {
        'original_receipt_id': receipt['id'],
        'returns': [
            {
                'original_line_id': receipt['lines'][0]['id'],
                'quantity': quantity,
                'condition': 'resellable',
            }
        ],
    }
    total = client.post(f'{RECEIPTS}quote', json=body).json()['total']
    return client.post(
        RECEIPTS, json={**body, 'payments': [], 'expected_total': total}
    )


# Rule 11


def test_a_void_mirrors_the_receipt_inside_its_open_shift(
    owner_client: TestClient,
    session: Session,
    owner: User,
    cashier: User,
    shirt: Sku,
) -> None:
    switch_to(owner_client, cashier)
    shift = open_shift(owner_client, 100000)
    receipt = sell(owner_client, (shirt, 2)).json()
    assert void(owner_client, receipt, '  ').status_code == 409

    response = void(owner_client, receipt, 'Pelanggan batal beli')
    assert response.status_code == 200, response.text
    voided = response.json()
    assert (voided['status'], voided['void_reason']) == (
        'voided',
        'Pelanggan batal beli',
    )
    movements = session.exec(
        select(StockMovement)
        .where(StockMovement.document_id == receipt['id'])
        .order_by(col(StockMovement.id))
    ).all()
    assert [(m.reason, m.quantity, m.value) for m in movements] == [
        (MovementReason.sale, -2, -100000),
        (MovementReason.reversal, 2, 100000),
    ]
    assert movements[1].document_number.startswith('BTL-')
    assert void(owner_client, receipt).status_code == 409
    # A voided Receipt can't be returned either (rule 12).
    response = owner_client.get(
        f'{RECEIPTS}for-return', params={'number': receipt['number']}
    )
    assert response.status_code == 409

    response = close_shift(owner_client, shift['id'], 100000)
    summary = response.json()
    assert summary['expected_cash'] == 100000
    assert (summary['sale_count'], summary['void_count']) == (0, 1)
    switch_to(owner_client, owner)
    assert stock_of(owner_client, shirt.id) == (10, 500000)


def test_only_its_cashier_or_the_owner_voids_and_only_while_open(
    owner_client: TestClient,
    session: Session,
    owner: User,
    cashier: User,
    shirt: Sku,
) -> None:
    switch_to(owner_client, cashier)
    shift = open_shift(owner_client)
    receipt = sell(owner_client, (shirt, 1)).json()
    other = sell(owner_client, (shirt, 1)).json()

    budi = make_user(session, 'budi', Role.cashier)
    switch_to(owner_client, budi)
    assert void(owner_client, receipt).status_code == 403
    admin = make_user(session, 'admin', Role.admin)
    switch_to(owner_client, admin)
    assert void(owner_client, receipt).status_code == 403

    switch_to(owner_client, owner)
    assert void(owner_client, receipt).status_code == 200
    switch_to(owner_client, cashier)
    close_shift(owner_client, shift['id'], 280000)
    response = void(owner_client, other)
    assert response.status_code == 409
    assert 'lewat retur' in response.json()['detail']


def test_a_returned_receipt_is_voided_only_after_its_return(
    owner_client: TestClient, shirt: Sku
) -> None:
    open_shift(owner_client)
    receipt = sell(owner_client, (shirt, 2)).json()
    returned = give_back(owner_client, receipt).json()
    response = void(owner_client, receipt)
    assert response.status_code == 409
    assert returned['number'] in response.json()['detail']
    assert void(owner_client, returned).status_code == 200
    assert void(owner_client, receipt).status_code == 200


# The closing summary


def test_the_closing_summary_adds_up_each_payment_method(
    owner_client: TestClient,
    session: Session,
    owner: User,
    cashier: User,
    shirt: Sku,
) -> None:
    switch_to(owner_client, cashier)
    shift = open_shift(owner_client, 100000)
    qris = method_id(owner_client, 'QRIS')
    sell(owner_client, (shirt, 1))
    receipt = sell(
        owner_client,
        (shirt, 2),
        payments=[
            {'payment_method_id': qris, 'amount': 160000, 'confirmed': True}
        ],
    ).json()
    give_back(owner_client, receipt)
    listed = owner_client.get(RECEIPTS, params={'shift_id': shift['id']})
    assert [r['kind'] for r in listed.json()['items']] == [
        'return',
        'sale',
        'sale',
    ]
    assert listed.json()['items'][1]['methods'] == 'QRIS'

    summary = close_shift(owner_client, shift['id'], 100000).json()
    assert [
        (t['method_name'], t['amount']) for t in summary['payment_totals']
    ] == [('Tunai', 0), ('QRIS', 160000)]
    assert (summary['sale_count'], summary['return_count']) == (2, 1)
    assert summary['net_sales'] == 160000

    # Another cashier can't read this Shift's Receipts.
    budi = make_user(session, 'budi', Role.cashier)
    switch_to(owner_client, budi)
    response = owner_client.get(RECEIPTS, params={'shift_id': shift['id']})
    assert response.status_code == 403


# Rule 3


def test_the_owner_decides_who_bears_a_short_drawer(
    owner_client: TestClient,
    session: Session,
    owner: User,
    cashier: User,
    shirt: Sku,
) -> None:
    switch_to(owner_client, cashier)
    first = open_shift(owner_client, 100000)
    sell(owner_client, (shirt, 1))
    close_shift(owner_client, first['id'], 170000)
    second = open_shift(owner_client, 100000)
    close_shift(owner_client, second['id'], 95000)
    resolution = f'{SHIFTS}{first["id"]}/resolution'
    response = owner_client.post(
        resolution, json={'resolution': 'company_loss'}
    )
    assert response.status_code == 403

    admin = make_user(session, 'admin', Role.admin)
    switch_to(owner_client, admin)
    waiting = owner_client.get(SHIFTS, params={'needs_resolution': True})
    assert [s['id'] for s in waiting.json()['items']] == [
        second['id'],
        first['id'],
    ]
    response = owner_client.post(
        resolution, json={'resolution': 'company_loss'}
    )
    assert response.status_code == 403

    switch_to(owner_client, owner)
    response = owner_client.post(
        resolution,
        json={'resolution': 'employee_charge', 'charged_user_id': cashier.id},
    )
    assert response.status_code == 200, response.text
    assert response.json()['charged_user_name'] == 'Ani'
    assert response.json()['needs_resolution'] is False
    response = owner_client.post(
        resolution, json={'resolution': 'company_loss'}
    )
    assert response.status_code == 409
    response = owner_client.post(
        f'{SHIFTS}{second["id"]}/resolution',
        json={'resolution': 'company_loss'},
    )
    assert response.json()['resolution'] == 'company_loss'

    charges = owner_client.get('/api/v1/employee-charges/').json()['items']
    assert [
        (c['user_name'], c['amount'], c['source_number']) for c in charges
    ] == [('Ani', 10000, first['number'])]
    assert (
        owner_client.get(SHIFTS, params={'needs_resolution': True}).json()[
            'total'
        ]
        == 0
    )
