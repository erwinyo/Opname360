"""Slice 3, rules 1-4 and 17: Shifts and the cash drawer."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import (
    SHIFTS,
    close_shift,
    make_user,
    open_shift,
    switch_to,
)

from opname360.models import Role, User


SETTINGS = '/api/v1/shop-settings/'
METHODS = '/api/v1/payment-methods/'


# Rule 1


def test_the_drawer_has_one_open_shift_at_a_time(
    owner_client: TestClient, session: Session
) -> None:
    ani = make_user(session, 'ani', Role.cashier)
    budi = make_user(session, 'budi', Role.cashier)
    switch_to(owner_client, ani)
    assert owner_client.get(f'{SHIFTS}current').json() is None
    shift = open_shift(owner_client, 300000)
    assert shift['number'].startswith('SH-')
    assert shift['is_mine'] is True

    switch_to(owner_client, budi)
    current = owner_client.get(f'{SHIFTS}current').json()
    assert (current['id'], current['is_mine']) == (shift['id'], False)
    response = owner_client.post(SHIFTS, json={'opening_float': 100000})
    assert response.status_code == 409
    assert 'Ani masih terbuka' in response.json()['detail']
    # Nor can Budi close Ani's Shift.
    assert close_shift(owner_client, shift['id'], 0).status_code == 403

    switch_to(owner_client, ani)
    assert close_shift(owner_client, shift['id'], 300000).status_code == 200
    switch_to(owner_client, budi)
    assert open_shift(owner_client, 100000)['cashier_name'] == 'Budi'


# Rule 2


def test_closing_is_a_blind_cash_count(
    owner_client: TestClient, session: Session
) -> None:
    ani = make_user(session, 'ani', Role.cashier)
    switch_to(owner_client, ani)
    shift = open_shift(owner_client, 250000)
    assert 'expected_cash' not in shift
    # Not even through the Shift itself while it is open.
    response = owner_client.get(f'{SHIFTS}{shift["id"]}')
    assert response.status_code == 403

    response = close_shift(owner_client, shift['id'], 240000)
    assert response.status_code == 200, response.text
    closed = response.json()
    assert closed['expected_cash'] == 250000
    assert closed['counted_cash'] == 240000
    assert closed['cash_variance'] == -10000
    assert closed['needs_resolution'] is True
    # Afterwards the Cashier can read the summary again, and close only once.
    assert owner_client.get(f'{SHIFTS}{shift["id"]}').status_code == 200
    assert close_shift(owner_client, shift['id'], 250000).status_code == 409


# Rule 4


def test_every_shift_starts_with_its_own_float(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    ani = make_user(session, 'ani', Role.cashier)
    switch_to(owner_client, ani)
    first = open_shift(owner_client, 300000)
    close_shift(owner_client, first['id'], 305000)
    second = open_shift(owner_client, 200000)
    response = close_shift(owner_client, second['id'], 200000)
    assert response.json()['expected_cash'] == 200000
    assert response.json()['cash_variance'] == 0

    # A cash surplus is a gain: nothing for the Owner to decide.
    switch_to(owner_client, owner)
    shifts = owner_client.get(SHIFTS).json()['items']
    assert [(s['cash_variance'], s['needs_resolution']) for s in shifts] == [
        (0, False),
        (5000, False),
    ]


# Rule 17


def test_an_admin_does_not_sell_and_a_cashier_stays_at_the_till(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    admin = make_user(session, 'admin', Role.admin)
    cashier = make_user(session, 'ani', Role.cashier)

    switch_to(owner_client, admin)
    response = owner_client.post(SHIFTS, json={'opening_float': 0})
    assert response.status_code == 403
    assert owner_client.get(f'{SHIFTS}current').status_code == 403

    switch_to(owner_client, cashier)
    assert owner_client.get(SHIFTS).status_code == 403
    assert owner_client.get('/api/v1/stock/').status_code == 403
    assert owner_client.get(SETTINGS).status_code == 200

    # The Owner can open and close the drawer too.
    switch_to(owner_client, owner)
    shift = open_shift(owner_client, 0)
    response = close_shift(owner_client, shift['id'], 0)
    assert response.status_code == 200, response.text


def test_the_owner_sets_up_the_shop_and_its_payment_methods(
    owner_client: TestClient, session: Session
) -> None:
    settings = owner_client.get(SETTINGS).json()
    assert settings['return_window_days'] == 7
    response = owner_client.put(
        SETTINGS,
        json={
            **settings,
            'name': 'Toko Seragam Maju',
            'receipt_footer': 'Terima kasih',
            'return_window_days': 14,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()['name'] == 'Toko Seragam Maju'
    closing_first = {**settings, 'opens_at': '21:00', 'closes_at': '08:00'}
    assert owner_client.put(SETTINGS, json=closing_first).status_code == 422

    methods = owner_client.get(METHODS).json()
    assert [(m['name'], m['is_cash']) for m in methods] == [
        ('Tunai', True),
        ('Transfer Bank', False),
        ('QRIS', False),
        ('Kartu', False),
    ]
    response = owner_client.post(METHODS, json={'name': 'gopay'})
    assert response.status_code == 201
    assert (
        owner_client.post(METHODS, json={'name': 'GoPay'}).status_code == 409
    )
    # Change and refunds need a cash method.
    response = owner_client.patch(
        f'{METHODS}{methods[0]["id"]}', json={'is_active': False}
    )
    assert response.status_code == 409
    response = owner_client.patch(
        f'{METHODS}{methods[2]["id"]}', json={'is_active': False}
    )
    assert response.status_code == 200
    active = owner_client.get(METHODS, params={'active_only': True}).json()
    assert 'QRIS' not in [m['name'] for m in active]

    cashier = make_user(session, 'ani', Role.cashier)
    switch_to(owner_client, cashier)
    assert owner_client.put(SETTINGS, json=settings).status_code == 403
    assert owner_client.post(METHODS, json={'name': 'OVO'}).status_code == 403
