"""Slice 3, rules 1, 2, 5-10 and 17: selling at the till."""

from decimal import Decimal

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import (
    RECEIPTS,
    SHIFTS,
    cart,
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

from opname360.models import (
    MovementReason,
    ReceiptLine,
    Role,
    Sku,
    StockMovement,
    User,
)


@pytest.fixture
def cashier(session: Session) -> User:
    return make_user(session, 'ani', Role.cashier)


@pytest.fixture
def shirt(owner_client: TestClient, session: Session) -> Sku:
    """Rp 80.000, 10 in stock at Rp 50.000."""
    sku = new_sku(owner_client, session, selling_price=80000)
    receive(owner_client, sku, 10, 50000)
    return sku


@pytest.fixture
def pen(owner_client: TestClient, session: Session) -> Sku:
    """Rp 3.500, nothing in stock yet; bought before at Rp 2.000."""
    sku = new_sku(owner_client, session, selling_price=3500)
    sku.latest_unit_cost = Decimal(2000)
    session.add(sku)
    session.commit()
    return sku


@pytest.fixture
def till(
    owner_client: TestClient, cashier: User, shirt: Sku, pen: Sku
) -> TestClient:
    """The cashier at the till with a Rp 200.000 Float."""
    switch_to(owner_client, cashier)
    open_shift(owner_client, 200000)
    return owner_client


# Rules 1 and 17


def test_selling_needs_an_open_shift_of_ones_own(
    owner_client: TestClient, session: Session, cashier: User, shirt: Sku
) -> None:
    switch_to(owner_client, cashier)
    response = sell(owner_client, (shirt, 1))
    assert response.status_code == 409
    assert 'Buka shift dulu' in response.json()['detail']

    open_shift(owner_client)
    other = make_user(session, 'budi', Role.cashier)
    switch_to(owner_client, other)
    assert sell(owner_client, (shirt, 1)).status_code == 403

    admin = make_user(session, 'admin', Role.admin)
    switch_to(owner_client, admin)
    response = owner_client.post(
        RECEIPTS, json={'lines': cart((shirt, 1)), 'expected_total': 80000}
    )
    assert response.status_code == 403
    response = owner_client.get(f'{RECEIPTS}skus', params={'search': 'x'})
    assert response.status_code == 403


# Rule 5


def test_a_scan_finds_one_sku_and_a_name_finds_several(
    till: TestClient, shirt: Sku, pen: Sku
) -> None:
    found = till.get(f'{RECEIPTS}skus', params={'search': shirt.barcode})
    assert [sku['id'] for sku in found.json()] == [shirt.id]
    assert 'latest_unit_cost' not in found.json()[0]
    found = till.get(f'{RECEIPTS}skus', params={'search': 'produk'})
    assert {sku['id'] for sku in found.json()} == {shirt.id, pen.id}

    # Scanning the same label again adds to its line.
    quote = till.post(
        f'{RECEIPTS}quote',
        json={'lines': cart((shirt, 1), (pen, 2), (shirt, 1))},
    ).json()
    assert [(line['sku_id'], line['quantity']) for line in quote['lines']] == [
        (shirt.id, '2'),
        (pen.id, '2'),
    ]
    assert quote['total'] == 167000


# Rule 6


def test_the_price_is_todays_selling_price_and_nothing_else(
    till: TestClient, owner: User, shirt: Sku
) -> None:
    lines = cart((shirt, 1))
    quoted = till.post(f'{RECEIPTS}quote', json={'lines': lines}).json()
    assert quoted['total'] == 80000

    # The Owner raises the price while the customer is at the counter.
    shirt.selling_price = 90000
    response = till.post(
        RECEIPTS,
        json={
            'lines': [{**lines[0], 'unit_price': 1000, 'discount': 79000}],
            'payments': [
                {'payment_method_id': method_id(till), 'amount': 80000}
            ],
            'expected_total': 80000,
        },
    )
    assert response.status_code == 409
    assert 'Rp 90.000' in response.json()['detail']
    receipt = sell(till, (shirt, 1)).json()
    assert (receipt['lines'][0]['unit_price'], receipt['total']) == (
        90000,
        90000,
    )


# Rule 8


def test_payment_can_be_split_and_change_comes_only_from_cash(
    till: TestClient, shirt: Sku
) -> None:
    cash, qris = method_id(till), method_id(till, 'QRIS')
    # Rp 160.000: Rp 100.000 by QRIS, Rp 100.000 in cash.
    split = [
        {'payment_method_id': qris, 'amount': 100000, 'confirmed': True},
        {'payment_method_id': cash, 'amount': 100000},
    ]
    receipt = sell(till, (shirt, 2), payments=split).json()
    assert receipt['change_given'] == 40000
    assert [(p['method_name'], p['amount']) for p in receipt['payments']] == [
        ('QRIS', 100000),
        ('Tunai', 60000),
    ]

    short = [{'payment_method_id': cash, 'amount': 50000}]
    response = sell(till, (shirt, 1), payments=short)
    assert response.status_code == 409
    assert 'kurang Rp 30.000' in response.json()['detail']
    too_much_card = [
        {'payment_method_id': qris, 'amount': 100000, 'confirmed': True}
    ]
    response = sell(till, (shirt, 1), payments=too_much_card)
    assert response.status_code == 409
    assert 'Kembalian hanya dari uang tunai' in response.json()['detail']
    unconfirmed = [{'payment_method_id': qris, 'amount': 80000}]
    response = sell(till, (shirt, 1), payments=unconfirmed)
    assert response.status_code == 409
    assert 'QRIS sudah masuk' in response.json()['detail']


# Rule 9


def test_a_sale_writes_its_stock_movements_and_cogs_even_into_negative(
    till: TestClient, session: Session, owner: User, shirt: Sku, pen: Sku
) -> None:
    receipt = sell(till, (shirt, 2), (pen, 3)).json()
    assert receipt['number'].startswith('PJ-')
    assert receipt['total'] == 170500

    movements = session.exec(
        select(StockMovement).where(StockMovement.document_id == receipt['id'])
    ).all()
    assert {
        (m.sku_id, m.reason, m.quantity, m.value, m.document_type)
        for m in movements
    } == {
        (shirt.id, MovementReason.sale, -2, -100000, 'receipt'),
        # Nothing in stock: sold anyway, at the latest unit cost.
        (pen.id, MovementReason.sale, -3, -6000, 'receipt'),
    }
    lines = {line['sku_id']: line for line in receipt['lines']}
    assert 'unit_cogs' not in lines[shirt.id]
    cogs = session.exec(
        select(ReceiptLine.sku_id, ReceiptLine.unit_cogs).where(
            ReceiptLine.receipt_id == receipt['id']
        )
    ).all()
    assert dict(cogs) == {shirt.id: 50000, pen.id: 2000}
    switch_to(till, owner)
    assert stock_of(till, pen.id) == (-3, -6000)


# Rule 2, with sales


def test_expected_cash_counts_cash_taken_and_change_given(
    till: TestClient, owner: User, shirt: Sku, pen: Sku
) -> None:
    cash, card = method_id(till), method_id(till, 'Kartu')
    sell(
        till,
        (shirt, 1),
        payments=[{'payment_method_id': cash, 'amount': 100000}],
    )
    sell(
        till,
        (pen, 2),
        payments=[
            {'payment_method_id': card, 'amount': 7000, 'confirmed': True}
        ],
    )
    shift = till.get(f'{SHIFTS}current').json()
    response = close_shift(till, shift['id'], 280000)
    # Float 200.000 + 80.000 in cash; the card payment is not in the drawer.
    assert response.json()['expected_cash'] == 280000
    assert response.json()['cash_variance'] == 0


# Rule 10


def test_a_reprinted_receipt_is_a_copy(till: TestClient, shirt: Sku) -> None:
    receipt = sell(till, (shirt, 1)).json()
    assert receipt['print_count'] == 0
    first = till.post(f'{RECEIPTS}{receipt["id"]}/print').json()
    again = till.post(f'{RECEIPTS}{receipt["id"]}/print').json()
    assert (first['print_count'], again['print_count']) == (1, 2)
