"""Slice 2, rules 12-17 and 21: Variance Resolution, approval, reversal."""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import (
    OPNAMES,
    count,
    lines_of,
    make_user,
    new_receipt,
    new_sku,
    new_supplier,
    open_opname,
    receipt_line,
    receive,
    stock_of,
    switch_to,
)

from opname360.models import (
    EmployeeCharge,
    Role,
    Sku,
    StockMovement,
    User,
)


CHARGES = '/api/v1/employee-charges/'


def reviewed(
    client: TestClient,
    session: Session,
    approver: User,
    counts: dict[int | None, float],
) -> tuple[dict, dict[int, dict]]:
    """A session over the given SKUs, counted as given, closed for Review
    by `approver`. Returns it with its lines by SKU id."""
    checker = make_user(session, f'checker{len(counts)}', Role.cashier)
    switch_to(client, approver)
    opname = open_opname(client, [checker], scope='skus', sku_ids=list(counts))
    switch_to(client, checker)
    for sku_id, quantity in counts.items():
        if quantity:
            assert (
                count(
                    client, opname['id'], sku_id=sku_id, quantity=quantity
                ).status_code
                == 201
            )
    switch_to(client, approver)
    uncounted = [
        line['id'] for line in lines_of(client, opname['id'], show='uncounted')
    ]
    if uncounted:
        client.post(
            f'{OPNAMES}{opname["id"]}/confirm-zero',
            json={'line_ids': uncounted},
        )
    response = client.post(f'{OPNAMES}{opname["id"]}/close-counting')
    assert response.status_code == 200, response.text
    return response.json(), {
        line['sku_id']: line for line in lines_of(client, opname['id'])
    }


def resolve(client: TestClient, opname: dict, line: dict, **decision):
    return client.put(
        f'{OPNAMES}{opname["id"]}/lines/{line["id"]}', json=decision
    )


def approve(client: TestClient, opname: dict):
    return client.post(f'{OPNAMES}{opname["id"]}/approve')


def opname_movements(session: Session, opname: dict) -> list[StockMovement]:
    return list(
        session.exec(
            select(StockMovement)
            .where(
                StockMovement.document_type == 'stock_opname',
                StockMovement.document_id == opname['id'],
            )
            .order_by(col(StockMovement.id))
        ).all()
    )


# Rule 12


def test_every_shortage_needs_a_reason_and_company_loss_is_the_default(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 5, 1000)
    opname, lines = reviewed(owner_client, session, owner, {sku.id: 3})

    response = approve(owner_client, opname)
    assert response.status_code == 409
    assert 'pilih alasan selisih kurang' in response.json()['detail']

    response = resolve(
        owner_client, opname, lines[sku.id], shortage_reason='lost'
    )
    assert response.status_code == 200, response.text
    response = approve(owner_client, opname)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'approved'
    [line] = lines_of(owner_client, opname['id'])
    assert line['resolution'] == 'company_loss'
    assert session.exec(select(EmployeeCharge)).all() == []


# Rule 13


def test_only_the_owner_charges_an_employee_and_can_change_the_amount(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    shirt = new_sku(owner_client, session)
    hat = new_sku(owner_client, session)
    receive(owner_client, shirt, 5, 1000)
    receive(owner_client, hat, 5, 2000)
    admin = make_user(session, 'sari', Role.admin)
    culprit = make_user(session, 'joko', Role.cashier)
    opname, lines = reviewed(
        owner_client, session, owner, {shirt.id: 3, hat.id: 4}
    )
    charge = {'shortage_reason': 'lost', 'resolution': 'employee_charge'}

    switch_to(owner_client, admin)
    response = resolve(
        owner_client,
        opname,
        lines[shirt.id],
        charged_user_id=culprit.id,
        **charge,
    )
    assert response.status_code == 403

    switch_to(owner_client, owner)
    response = resolve(
        owner_client,
        opname,
        lines[shirt.id],
        charged_user_id=culprit.id,
        **charge,
    )
    assert response.status_code == 200, response.text
    assert response.json()['charged_user_name'] == 'Joko'
    resolve(
        owner_client,
        opname,
        lines[hat.id],
        charged_user_id=culprit.id,
        charge_amount=1500,
        **charge,
    )
    # An Admin who approves keeps the Owner's decision.
    switch_to(owner_client, admin)
    response = resolve(
        owner_client,
        opname,
        lines[hat.id],
        charged_user_id=culprit.id,
        charge_amount=1500,
        **charge,
    )
    assert response.status_code == 200, response.text
    assert approve(owner_client, opname).status_code == 200

    charges = session.exec(
        select(EmployeeCharge).order_by(col(EmployeeCharge.amount))
    ).all()
    # 2 shirts at Rp 1.000 by default; the hat as the Owner set it.
    assert [(c.user_id, c.amount) for c in charges] == [
        (culprit.id, 1500),
        (culprit.id, 2000),
    ]
    assert charges[1].source_number == opname['number']

    switch_to(owner_client, owner)
    totals = owner_client.get(f'{CHARGES}totals').json()
    assert totals == [
        {
            'user_id': culprit.id,
            'full_name': 'Joko',
            'outstanding_amount': 3500,
            'outstanding_count': 2,
        }
    ]
    page = owner_client.get(CHARGES, params={'user_id': culprit.id}).json()
    assert page['total'] == 2
    switch_to(owner_client, admin)
    assert owner_client.get(CHARGES).status_code == 403


def test_a_charge_needs_an_employee(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 5, 1000)
    opname, lines = reviewed(owner_client, session, owner, {sku.id: 4})
    resolve(
        owner_client,
        opname,
        lines[sku.id],
        shortage_reason='lost',
        resolution='employee_charge',
    )
    response = approve(owner_client, opname)
    assert response.status_code == 409
    assert 'pilih karyawan' in response.json()['detail']


# Rule 14


def test_a_surplus_is_valued_by_costing_rule_5(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    average = new_sku(owner_client, session)
    receive(owner_client, average, 10, 5000)
    receive(owner_client, average, 10, 6000)
    fifo = new_sku(owner_client, session, 'fifo')
    receive(owner_client, fifo, 1, 5000)
    receive(owner_client, fifo, 1, 7000)
    opname, _ = reviewed(
        owner_client, session, owner, {average.id: 21, fifo.id: 3}
    )

    assert approve(owner_client, opname).status_code == 200
    by_sku = {m.sku_id: m for m in opname_movements(session, opname)}
    # Moving Average at the average cost; FIFO at the latest unit cost.
    assert by_sku[average.id].value == 5500
    assert by_sku[fifo.id].value == 7000
    assert stock_of(owner_client, average.id) == (21, 115500)
    assert stock_of(owner_client, fifo.id) == (3, 19000)


def test_a_surplus_of_a_sku_that_never_had_a_cost_needs_one(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    opname, lines = reviewed(owner_client, session, owner, {sku.id: 2})
    [line] = lines_of(owner_client, opname['id'], show='needs_cost')
    assert line['needs_cost'] is True

    response = approve(owner_client, opname)
    assert response.status_code == 409
    assert 'isi harga per pcs' in response.json()['detail']

    resolve(owner_client, opname, lines[sku.id], unit_cost=4000)
    assert lines_of(owner_client, opname['id'], show='needs_cost') == []
    assert approve(owner_client, opname).status_code == 200
    assert stock_of(owner_client, sku.id) == (2, 8000)
    session.refresh(sku)
    assert sku.latest_unit_cost == 4000


# Rule 15


def test_approval_adjusts_by_the_variance_on_top_of_todays_stock(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(sku.id, 5, 1000)]
    )
    # Snapshot 5, counted 4.
    opname, lines = reviewed(owner_client, session, owner, {sku.id: 4})
    assert stock_of(owner_client, sku.id) == (5, 5000)

    # One more leaves before approval: the system now says 4.
    response = owner_client.post(
        '/api/v1/supplier-returns/',
        json={
            'goods_receipt_id': receipt['id'],
            'returned_on': '2026-11-16',
            'lines': [
                {
                    'goods_receipt_line_id': receipt['lines'][0]['id'],
                    'quantity': 1,
                }
            ],
        },
    )
    owner_client.post(
        f'/api/v1/supplier-returns/{response.json()["id"]}/complete'
    )
    assert stock_of(owner_client, sku.id) == (4, 4000)

    resolve(owner_client, opname, lines[sku.id], shortage_reason='unknown')
    assert approve(owner_client, opname).status_code == 200
    [movement] = opname_movements(session, opname)
    assert (movement.quantity, movement.value) == (-1, -1000)
    assert movement.reason == 'opname'
    assert stock_of(owner_client, sku.id) == (3, 3000)


# Rule 16


def test_an_approved_session_is_immutable(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 5, 1000)
    opname, lines = reviewed(owner_client, session, owner, {sku.id: 5})
    assert approve(owner_client, opname).status_code == 200
    # No Variance, no Stock Movement.
    assert opname_movements(session, opname) == []

    url = f'{OPNAMES}{opname["id"]}'
    assert approve(owner_client, opname).status_code == 409
    assert owner_client.post(f'{url}/cancel').status_code == 409
    assert owner_client.post(f'{url}/close-counting').status_code == 409
    assert (
        owner_client.post(
            f'{url}/lines/{lines[sku.id]["id"]}/recount'
        ).status_code
        == 409
    )
    assert resolve(owner_client, opname, lines[sku.id]).status_code == 409


# Rule 17


def test_reversal_undoes_the_adjustments_and_outstanding_charges(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    shirt = new_sku(owner_client, session)
    hat = new_sku(owner_client, session)
    receive(owner_client, shirt, 5, 1000)
    receive(owner_client, hat, 5, 2000)
    culprit = make_user(session, 'joko', Role.cashier)
    opname, lines = reviewed(
        owner_client, session, owner, {shirt.id: 3, hat.id: 6}
    )
    resolve(
        owner_client,
        opname,
        lines[shirt.id],
        shortage_reason='lost',
        resolution='employee_charge',
        charged_user_id=culprit.id,
    )
    assert approve(owner_client, opname).status_code == 200
    assert stock_of(owner_client, shirt.id) == (3, 3000)
    assert stock_of(owner_client, hat.id) == (6, 12000)

    response = owner_client.post(
        f'{OPNAMES}{opname["id"]}/reverse', json={'reason': 'Salah lokasi'}
    )
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'reversed'
    assert response.json()['reversal']['number'].startswith('BTL-')
    assert stock_of(owner_client, shirt.id) == (5, 5000)
    assert stock_of(owner_client, hat.id) == (5, 10000)
    [charge] = session.exec(select(EmployeeCharge)).all()
    session.refresh(charge)
    assert charge.status == 'cancelled'
    assert owner_client.get(f'{CHARGES}totals').json() == []
    response = owner_client.post(
        f'{OPNAMES}{opname["id"]}/reverse', json={'reason': 'Lagi'}
    )
    assert response.status_code == 409


# Rule 21


def test_damaged_stock_is_written_off_with_a_partial_opname(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 10, 3000)
    # Two found torn: count only the good ones.
    opname, lines = reviewed(owner_client, session, owner, {sku.id: 8})
    resolve(owner_client, opname, lines[sku.id], shortage_reason='damaged')
    assert approve(owner_client, opname).status_code == 200

    card = owner_client.get(f'/api/v1/stock/skus/{sku.id}/card').json()
    latest = card['items'][0]
    assert latest['reason'] == 'opname'
    assert latest['document_number'] == opname['number']
    assert Decimal(latest['quantity']) == -2
    assert Decimal(latest['value']) == -6000
    stored = session.get(Sku, sku.id)
    assert stored is not None
