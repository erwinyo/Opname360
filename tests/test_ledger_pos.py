"""Slice 5, rules 4, 7, 8 and 15: sales, returns, Voids and Shifts in the
Ledger."""

from decimal import Decimal

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from .conftest import (
    RECEIPTS,
    SHIFTS,
    account_balance,
    close_shift,
    give_back,
    make_user,
    method_id,
    new_receipt,
    new_sku,
    new_supplier,
    open_shift,
    posted,
    promote,
    receipt_line,
    receive,
    sell,
    stock_value,
    switch_to,
)
from .test_supplier_returns import new_return

from opname360.models import (
    JournalEntry,
    JournalLine,
    Role,
    Sku,
    User,
)
from opname360.services import posting
from opname360.services.documents import shop_now


LEDGER = '/api/v1/ledger/'
GROSS_PROFIT = (
    'Penjualan',
    'Diskon Penjualan',
    'Retur Penjualan',
    'Harga Pokok Penjualan',
)


@pytest.fixture
def cashier(session: Session) -> User:
    return make_user(session, 'ani', Role.cashier)


@pytest.fixture
def shirt(owner_client: TestClient, session: Session) -> Sku:
    """Rp 80.000 with 10% off; 10 in stock at Rp 50.000."""
    sku = new_sku(owner_client, session, selling_price=80000)
    receive(owner_client, sku, 10, 50000)
    promote(owner_client, 'skus', [sku.id], value=10)
    return sku


@pytest.fixture
def till(owner_client: TestClient, cashier: User, shirt: Sku) -> TestClient:
    switch_to(owner_client, cashier)
    open_shift(owner_client, 200000)
    return owner_client


def test_a_sale_and_its_cost(
    till: TestClient, session: Session, shirt: Sku
) -> None:
    """Rp 160.000 less Rp 16.000 off, paid Rp 100.000 cash and the rest by
    QRIS; the shirts cost Rp 100.000."""
    receipt = sell(
        till,
        (shirt, 2),
        payments=[
            {'payment_method_id': method_id(till), 'amount': 100000},
            {
                'payment_method_id': method_id(till, 'QRIS'),
                'amount': 44000,
                'confirmed': True,
            },
        ],
    ).json()
    assert posted(session, 'receipt', receipt['id']) == {
        'Penjualan': -160000,
        'Diskon Penjualan': 16000,
        'Kas Kasir': 100000,
        'Bank': 44000,
        'Harga Pokok Penjualan': 100000,
        'Persediaan': -100000,
    }


def test_returns_resellable_and_damaged(
    till: TestClient, session: Session, shirt: Sku
) -> None:
    sale = sell(till, (shirt, 2)).json()
    back = give_back(till, sale, [(0, 1, 'resellable')]).json()
    assert posted(session, 'receipt', back['id']) == {
        'Retur Penjualan': 72000,
        'Kas Kasir': -72000,
        'Persediaan': 50000,
        'Harga Pokok Penjualan': -50000,
    }
    damaged = give_back(till, sale, [(0, 1, 'damaged')]).json()
    assert posted(session, 'receipt', damaged['id']) == {
        'Retur Penjualan': 72000,
        'Kas Kasir': -72000,
        'Barang Rusak': 50000,
        'Harga Pokok Penjualan': -50000,
    }


def test_an_exchange_and_a_void(
    till: TestClient, owner_client: TestClient, session: Session, shirt: Sku
) -> None:
    switch_to(
        owner_client,
        session.exec(select(User).where(User.role == Role.owner)).one(),
    )
    tie = new_sku(owner_client, session, selling_price=100000)
    receive(owner_client, tie, 3, 60000)
    switch_to(
        owner_client,
        session.exec(select(User).where(User.username == 'ani')).one(),
    )
    sale = sell(till, (shirt, 1)).json()
    swap = give_back(
        till, sale, [(0, 1, 'resellable')], new=((tie, 1),)
    ).json()
    # Rp 100.000 for the tie, Rp 72.000 back for the shirt: 28.000 in cash.
    assert posted(session, 'receipt', swap['id']) == {
        'Penjualan': -100000,
        'Retur Penjualan': 72000,
        'Kas Kasir': 28000,
        'Harga Pokok Penjualan': 10000,
        'Persediaan': -10000,
    }
    response = till.post(
        f'{RECEIPTS}{swap["id"]}/void', json={'reason': 'Salah'}
    )
    assert response.status_code == 200, response.text
    assert posted(session, 'receipt', swap['id']) == {}


def test_a_shift_from_float_to_close(
    owner_client: TestClient,
    session: Session,
    owner: User,
    cashier: User,
    shirt: Sku,
) -> None:
    """Rule 8: Kas Kasir is zero whenever no Shift is open."""
    switch_to(owner_client, cashier)
    shift = open_shift(owner_client, 200000)
    assert posted(session, 'shift', shift['id'], 'open') == {
        'Kas Kasir': 200000,
        'Kas Besar': -200000,
    }
    sale = sell(owner_client, (shirt, 1)).json()
    give_back(owner_client, sale, [(0, 1, 'resellable')])
    voided = sell(owner_client, (shirt, 2)).json()
    owner_client.post(
        f'{RECEIPTS}{voided["id"]}/void', json={'reason': 'Batal'}
    )
    # Expected 200.000 + 72.000 - 72.000; 5.000 is missing.
    assert close_shift(owner_client, shift['id'], 195000).status_code == 200
    assert posted(session, 'shift', shift['id'], 'close') == {
        'Kas Besar': 195000,
        'Selisih Kurang Kas': 5000,
        'Kas Kasir': -200000,
    }
    assert account_balance(session, 'Kas Kasir') == 0

    switch_to(owner_client, owner)
    response = owner_client.post(
        f'{SHIFTS}{shift["id"]}/resolution',
        json={'resolution': 'employee_charge', 'charged_user_id': cashier.id},
    )
    assert response.status_code == 200, response.text
    assert posted(session, 'shift', shift['id'], 'resolve') == {
        'Piutang Karyawan': 5000,
        'Selisih Kurang Kas': -5000,
    }

    # Counted more than expected: Selisih Lebih Kas.
    switch_to(owner_client, cashier)
    second = open_shift(owner_client, 100000)
    close_shift(owner_client, second['id'], 102000)
    assert posted(session, 'shift', second['id'], 'close') == {
        'Kas Besar': 102000,
        'Kas Kasir': -100000,
        'Selisih Lebih Kas': -2000,
    }
    assert account_balance(session, 'Kas Kasir') == 0


def test_the_owner_chooses_each_methods_account(
    owner_client: TestClient, session: Session, owner: User, shirt: Sku
) -> None:
    """Rule 15."""
    bca = owner_client.post(
        f'{LEDGER}accounts',
        json={
            'code': '1104',
            'name': 'Bank BCA',
            'type': 'asset',
            'is_cash': True,
        },
    ).json()
    qris = method_id(owner_client, 'QRIS')
    url = f'/api/v1/payment-methods/{qris}'
    response = owner_client.patch(url, json={'account_id': bca['id']})
    assert response.status_code == 200, response.text
    assert response.json()['account_id'] == bca['id']
    cash = method_id(owner_client)
    refused = owner_client.patch(
        f'/api/v1/payment-methods/{cash}', json={'account_id': bca['id']}
    )
    assert refused.status_code == 409

    open_shift(owner_client)
    receipt = sell(
        owner_client,
        (shirt, 1),
        payments=[
            {'payment_method_id': qris, 'amount': 72000, 'confirmed': True}
        ],
    ).json()
    assert posted(session, 'receipt', receipt['id'])['Bank BCA'] == 72000

    switch_to(owner_client, make_user(session, 'admin-akun', Role.admin))
    assert (
        owner_client.patch(url, json={'account_id': None}).status_code == 403
    )


def test_the_owner_moves_a_system_account(
    owner_client: TestClient, session: Session, shirt: Sku
) -> None:
    """Rule 15: only the Owner; the accounts tied to stock, the drawer,
    debts and charges stay once used."""
    chart = {
        a['name']: a for a in owner_client.get(f'{LEDGER}accounts').json()
    }
    gifts = owner_client.post(
        f'{LEDGER}accounts',
        json={
            'code': '4204',
            'name': 'Pendapatan Lain-lain',
            'type': 'revenue',
        },
    ).json()
    response = owner_client.put(
        f'{LEDGER}roles/other_income', json={'account_id': gifts['id']}
    )
    assert response.status_code == 200, response.text
    chart = {
        a['name']: a for a in owner_client.get(f'{LEDGER}accounts').json()
    }
    assert chart['Pendapatan Lain-lain']['role'] == 'other_income'
    assert chart['Pendapatan Lain']['role'] is None
    # The wrong type of account can't play a role.
    wrong = owner_client.put(
        f'{LEDGER}roles/cogs', json={'account_id': chart['Sewa']['id']}
    )
    assert wrong.status_code == 409
    # Persediaan has entries: it keeps its role.
    other = owner_client.post(
        f'{LEDGER}accounts',
        json={'code': '1202', 'name': 'Persediaan Gudang', 'type': 'asset'},
    ).json()
    stuck = owner_client.put(
        f'{LEDGER}roles/inventory', json={'account_id': other['id']}
    )
    assert stuck.status_code == 409

    switch_to(owner_client, make_user(session, 'admin-peran', Role.admin))
    response = owner_client.put(
        f'{LEDGER}roles/other_income',
        json={'account_id': chart['Pendapatan Lain']['id']},
    )
    assert response.status_code == 403


def test_gross_profit_in_the_ledger_matches_the_reports(
    till: TestClient,
    owner_client: TestClient,
    session: Session,
    owner: User,
    cashier: User,
    shirt: Sku,
) -> None:
    """Rule 7, for a day with a sale, a damaged return, a Void, Negative
    Stock filled and a Supplier Return at a cost other than stock's."""
    switch_to(owner_client, owner)
    pen = new_sku(owner_client, session, selling_price=3500)
    pen.latest_unit_cost = Decimal(2000)
    session.add(pen)
    session.commit()
    switch_to(owner_client, cashier)
    sale = sell(till, (shirt, 3), (pen, 4)).json()
    give_back(till, sale, [(0, 1, 'damaged')])
    voided = sell(till, (shirt, 1)).json()
    till.post(f'{RECEIPTS}{voided["id"]}/void', json={'reason': 'Batal'})
    switch_to(owner_client, owner)
    supplier = new_supplier(owner_client)
    received = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(pen.id, 10, 2600), receipt_line(shirt.id, 4, 65000)],
        payment_status='owed',
    )
    new_return(owner_client, received, [0, 2])

    today = shop_now().date()
    report = owner_client.get(
        '/api/v1/reports/sales',
        params={'start': str(today), 'end': str(today)},
    ).json()
    in_ledger = -sum(
        (account_balance(session, name) for name in GROSS_PROFIT), Decimal(0)
    )
    assert in_ledger == Decimal(report['total']['gross_profit'])
    assert account_balance(session, 'Persediaan') == stock_value(session)


def test_backfill_posts_sales_and_shifts_too(
    till: TestClient,
    owner_client: TestClient,
    session: Session,
    owner: User,
    shirt: Sku,
) -> None:
    """Rule 5."""
    sale = sell(till, (shirt, 2)).json()
    give_back(till, sale, [(0, 1, 'resellable')])
    voided = sell(till, (shirt, 1)).json()
    till.post(f'{RECEIPTS}{voided["id"]}/void', json={'reason': 'Batal'})
    shift_id = sale['shift_id']
    close_shift(till, shift_id, 200000)
    expected = {
        (entry.document_type, entry.document_id, entry.event)
        for entry in session.exec(select(JournalEntry)).all()
    }
    session.exec(delete(JournalLine))  # ty: ignore[no-matching-overload]
    session.exec(delete(JournalEntry))  # ty: ignore[no-matching-overload]
    session.commit()

    posting.backfill(session)

    assert {
        (entry.document_type, entry.document_id, entry.event)
        for entry in session.exec(select(JournalEntry)).all()
    } == expected
    assert account_balance(session, 'Kas Kasir') == 0
    assert account_balance(session, 'Persediaan') == stock_value(session)
