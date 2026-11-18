"""Slice 5, rules 4, 8-11 and 15: Cash-outs, transfers, supplier payments,
settling Employee Charges and opening balances."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import (
    SHIFTS,
    account_balance,
    close_shift,
    make_user,
    new_receipt,
    new_sku,
    new_supplier,
    open_shift,
    posted,
    receipt_line,
    sell,
    switch_to,
)
from .test_supplier_returns import new_return

from opname360.models import Account, Role, User
from opname360.services.documents import shop_now


CASH = '/api/v1/cash/'
PAYMENTS = '/api/v1/supplier-payments/'
LEDGER = '/api/v1/ledger/'
GOODS = '/api/v1/goods-receipts/'


def account(session: Session, name: str) -> int:
    found = session.exec(select(Account).where(Account.name == name)).one()
    assert found.id is not None
    return found.id


def today(days_ago: int = 0) -> str:
    return str(shop_now().date() - timedelta(days=days_ago))


def cash_out(
    client: TestClient,
    session: Session,
    paid_from: str,
    amount: int,
    expense: str = 'Perlengkapan',
    **body: object,
):
    return client.post(
        f'{CASH}outs',
        json={
            'paid_on': today(),
            'paid_from_account_id': account(session, paid_from),
            'expense_account_id': account(session, expense),
            'amount': amount,
            'description': 'Kantong plastik',
            **body,
        },
    )


def test_a_cash_out_from_kas_besar(
    owner_client: TestClient, session: Session
) -> None:
    response = cash_out(owner_client, session, 'Kas Besar', 150000)
    assert response.status_code == 201, response.text
    paid = response.json()
    assert paid['number'].startswith('KK-')
    assert posted(session, 'cash_out', paid['id']) == {
        'Perlengkapan': 150000,
        'Kas Besar': -150000,
    }
    # Not from a non-cash account, nor to one only documents move.
    assert (
        cash_out(owner_client, session, 'Persediaan', 1000).status_code == 409
    )
    wrong = cash_out(
        owner_client, session, 'Kas Besar', 1000, expense='Persediaan'
    )
    assert wrong.status_code == 409
    future = cash_out(
        owner_client,
        session,
        'Kas Besar',
        1000,
        paid_on=str(shop_now().date() + timedelta(days=1)),
    )
    assert future.status_code == 409


def test_a_cash_out_from_the_drawer_lowers_expected_cash(
    owner_client: TestClient, session: Session
) -> None:
    """Rules 8 and 9."""
    assert (
        cash_out(owner_client, session, 'Kas Kasir', 20000).status_code == 409
    )
    shirt = new_sku(owner_client, session, selling_price=72000)
    shift = open_shift(owner_client, 200000)
    sell(owner_client, (shirt, 1))
    yesterday = cash_out(
        owner_client, session, 'Kas Kasir', 5000, paid_on=today(1)
    )
    assert yesterday.status_code == 409
    paid = cash_out(owner_client, session, 'Kas Kasir', 20000).json()
    assert paid['shift_number'] == shift['number']
    mistake = cash_out(owner_client, session, 'Kas Kasir', 7000).json()
    response = owner_client.post(
        f'{CASH}outs/{mistake["id"]}/reverse', json={'reason': 'Dobel'}
    )
    assert response.status_code == 200, response.text
    shown = owner_client.get(f'{SHIFTS}{shift["id"]}').json()
    assert shown['expected_cash'] == 200000 + 72000 - 20000

    assert close_shift(owner_client, shift['id'], 252000).status_code == 200
    closed = owner_client.get(f'{SHIFTS}{shift["id"]}').json()
    assert closed['cash_variance'] == 0
    assert account_balance(session, 'Kas Kasir') == 0
    late = owner_client.post(
        f'{CASH}outs/{paid["id"]}/reverse', json={'reason': 'Telat'}
    )
    assert late.status_code == 409


def test_a_transfer_between_cash_and_bank(
    owner_client: TestClient, session: Session
) -> None:
    response = owner_client.post(
        f'{CASH}transfers',
        json={
            'transferred_on': today(),
            'from_account_id': account(session, 'Kas Besar'),
            'to_account_id': account(session, 'Bank'),
            'amount': 2000000,
            'description': 'Setor ke bank',
        },
    )
    assert response.status_code == 201, response.text
    transfer = response.json()
    assert posted(session, 'cash_transfer', transfer['id']) == {
        'Bank': 2000000,
        'Kas Besar': -2000000,
    }
    drawer = owner_client.post(
        f'{CASH}transfers',
        json={
            'transferred_on': today(),
            'from_account_id': account(session, 'Kas Kasir'),
            'to_account_id': account(session, 'Bank'),
            'amount': 1000,
        },
    )
    assert drawer.status_code == 409
    response = owner_client.post(
        f'{CASH}transfers/{transfer["id"]}/reverse', json={'reason': 'Salah'}
    )
    assert response.status_code == 200
    assert posted(session, 'cash_transfer', transfer['id']) == {}


def test_paying_a_supplier_up_to_what_is_owed(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 10."""
    shirt = new_sku(owner_client, session)
    supplier = new_supplier(owner_client, 'CV Kain Jaya')
    other = new_supplier(owner_client, 'CV Lain')
    first = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 10, 10000)],
        payment_status='owed',
    )
    second = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 5, 10000)],
        payment_status='owed',
    )
    foreign = new_receipt(
        owner_client,
        other['id'],
        [receipt_line(shirt.id, 1, 10000)],
        payment_status='owed',
    )
    new_return(owner_client, first, [1])

    def pay(*lines: tuple[dict | None, int]):
        return owner_client.post(
            PAYMENTS,
            json={
                'supplier_id': supplier['id'],
                'paid_on': today(),
                'lines': [
                    {
                        'goods_receipt_id': receipt['id'] if receipt else None,
                        'amount': amount,
                    }
                    for receipt, amount in lines
                ],
            },
        )

    [debt] = owner_client.get(
        PAYMENTS + 'debts', params={'supplier_id': supplier['id']}
    ).json()
    assert [(row['number'], row['owed']) for row in debt['receipts']] == [
        (first['number'], 90000),
        (second['number'], 50000),
    ]
    assert pay((first, 90001)).status_code == 409
    assert pay((foreign, 1000)).status_code == 409
    response = pay((first, 90000), (second, 20000))
    assert response.status_code == 201, response.text
    payment = response.json()
    assert posted(session, 'supplier_payment', payment['id']) == {
        'Hutang Usaha': 110000,
        'Kas Besar': -110000,
    }
    assert owner_client.get(f'{GOODS}{first["id"]}').json()['owed_amount'] == 0
    assert (
        owner_client.get(f'{GOODS}{second["id"]}').json()['owed_amount']
        == 30000
    )
    assert pay((second, 30001)).status_code == 409

    response = owner_client.post(
        f'{PAYMENTS}{payment["id"]}/reverse', json={'reason': 'Salah jumlah'}
    )
    assert response.status_code == 200, response.text
    assert (
        owner_client.get(f'{GOODS}{first["id"]}').json()['owed_amount']
        == 90000
    )


def test_opening_balances_once_against_saldo_awal(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 11, including a debt that can then be paid."""
    supplier = new_supplier(owner_client, 'CV Lama')
    body = {
        'entry_date': today(5),
        'lines': [
            {'account_id': account(session, 'Kas Besar'), 'debit': 5000000},
            {'account_id': account(session, 'Bank'), 'debit': 20000000},
            {
                'account_id': account(session, 'Hutang Usaha'),
                'credit': 3000000,
                'supplier_id': supplier['id'],
            },
        ],
    }
    response = owner_client.post(f'{LEDGER}opening-balances', json=body)
    assert response.status_code == 201, response.text
    lines = {
        line['account_name']: (line['debit'], line['credit'])
        for line in response.json()['lines']
    }
    assert lines['Saldo Awal'] == ('0.0000', '22000000.0000')
    assert (
        owner_client.post(f'{LEDGER}opening-balances', json=body).status_code
        == 409
    )
    read = owner_client.get(f'{LEDGER}opening-balances').json()
    assert read['source'] == 'opening'

    # The opening debt is paid like a receipt.
    [debt] = owner_client.get(
        PAYMENTS + 'debts', params={'supplier_id': supplier['id']}
    ).json()
    assert debt['owed'] == 3000000
    response = owner_client.post(
        PAYMENTS,
        json={
            'supplier_id': supplier['id'],
            'paid_on': today(),
            'paid_from_account_id': account(session, 'Bank'),
            'lines': [{'goods_receipt_id': None, 'amount': 1000000}],
        },
    )
    assert response.status_code == 201, response.text
    [debt] = owner_client.get(
        PAYMENTS + 'debts', params={'supplier_id': supplier['id']}
    ).json()
    assert debt['owed'] == 2000000


def test_opening_balances_leave_stock_to_the_opname(
    owner_client: TestClient, session: Session
) -> None:
    response = owner_client.post(
        f'{LEDGER}opening-balances',
        json={
            'entry_date': today(),
            'lines': [
                {'account_id': account(session, 'Persediaan'), 'debit': 1}
            ],
        },
    )
    assert response.status_code == 409
    switch_to(owner_client, make_user(session, 'admin-saldo', Role.admin))
    response = owner_client.post(
        f'{LEDGER}opening-balances',
        json={
            'entry_date': today(),
            'lines': [{'account_id': account(session, 'Bank'), 'debit': 1}],
        },
    )
    assert response.status_code == 403


def test_settling_an_employee_charge(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    cashier = make_user(session, 'budi', Role.cashier)
    switch_to(owner_client, cashier)
    shift = open_shift(owner_client, 100000)
    close_shift(owner_client, shift['id'], 90000)
    switch_to(owner_client, owner)
    owner_client.post(
        f'{SHIFTS}{shift["id"]}/resolution',
        json={'resolution': 'employee_charge', 'charged_user_id': cashier.id},
    )
    [charge] = owner_client.get('/api/v1/employee-charges/').json()['items']
    url = f'/api/v1/employee-charges/{charge["id"]}/settle'

    switch_to(owner_client, make_user(session, 'admin-gaji', Role.admin))
    assert owner_client.post(url, json={'by_salary': True}).status_code == 403
    switch_to(owner_client, owner)
    response = owner_client.post(url, json={'by_salary': True})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'settled'
    assert posted(session, 'employee_charge', charge['id'], 'settle') == {
        'Gaji': 10000,
        'Piutang Karyawan': -10000,
    }
    assert account_balance(session, 'Piutang Karyawan') == 0
    assert owner_client.post(url, json={}).status_code == 409


def test_a_cashier_records_no_money(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 15."""
    switch_to(owner_client, make_user(session, 'kasir-kas', Role.cashier))
    assert owner_client.get(f'{CASH}outs').status_code == 403
    assert owner_client.get(PAYMENTS).status_code == 403
