"""Slice 5, rules 1, 2 and 15: accounts and journal entries."""

from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_user, switch_to

from opname360.models import Role
from opname360.services.documents import shop_now


LEDGER = '/api/v1/ledger/'


def accounts(client: TestClient) -> dict[str, dict]:
    return {a['name']: a for a in client.get(f'{LEDGER}accounts').json()}


def line(account: dict, debit: float = 0, credit: float = 0) -> dict:
    return {'account_id': account['id'], 'debit': debit, 'credit': credit}


def manual(client: TestClient, *lines: dict, days_ago: int = 0, **extra):
    day = shop_now().date() - timedelta(days=days_ago)
    return client.post(
        f'{LEDGER}journal',
        json={
            'entry_date': str(day),
            'description': 'Setoran modal',
            'lines': list(lines),
            **extra,
        },
    )


def test_an_entry_must_balance(owner_client: TestClient) -> None:
    """Rule 1."""
    chart = accounts(owner_client)
    response = manual(
        owner_client,
        line(chart['Bank'], debit=1000000),
        line(chart['Modal'], credit=900000),
    )
    assert response.status_code == 409
    assert 'tidak seimbang' in response.json()['detail']
    response = manual(
        owner_client,
        line(chart['Bank'], debit=1000000),
        line(chart['Modal'], credit=1000000),
    )
    assert response.status_code == 201, response.text
    entry = response.json()
    assert entry['number'].startswith('JR-')
    assert [
        (x['account_name'], x['debit'], x['credit']) for x in entry['lines']
    ] == [
        ('Bank', '1000000.0000', '0.0000'),
        ('Modal', '0.0000', '1000000.0000'),
    ]
    # A line is a debit or a credit, never both.
    response = manual(
        owner_client,
        line(chart['Bank'], debit=5, credit=5),
        line(chart['Modal'], credit=0),
    )
    assert response.status_code == 422


def test_entries_are_never_changed_only_mirrored(
    owner_client: TestClient,
) -> None:
    """Rule 2."""
    chart = accounts(owner_client)
    entry = manual(
        owner_client,
        line(chart['Prive'], debit=250000),
        line(chart['Kas Besar'], credit=250000),
    ).json()
    url = f'{LEDGER}journal/{entry["id"]}'
    assert owner_client.put(url, json={}).status_code == 405
    assert owner_client.delete(url).status_code == 405

    response = owner_client.post(f'{url}/reverse', json={'reason': 'Salah'})
    assert response.status_code == 200, response.text
    mirror = response.json()
    assert mirror['reverses_number'] == entry['number']
    assert [
        (x['account_name'], x['debit'], x['credit']) for x in mirror['lines']
    ] == [
        ('Kas Besar', '250000.0000', '0.0000'),
        ('Prive', '0.0000', '250000.0000'),
    ]
    assert (
        owner_client.get(url).json()['reversed_by_number'] == mirror['number']
    )
    again = owner_client.post(f'{url}/reverse', json={'reason': 'Lagi'})
    assert again.status_code == 409
    back = owner_client.post(
        f'{LEDGER}journal/{mirror["id"]}/reverse', json={'reason': 'Lagi'}
    )
    assert back.status_code == 409
    assert accounts(owner_client)['Prive']['balance'] == '0.0000'


def test_typed_entries_leave_the_system_accounts_alone(
    owner_client: TestClient,
) -> None:
    chart = accounts(owner_client)
    for name in ('Persediaan', 'Kas Kasir', 'Piutang Karyawan', 'Saldo Awal'):
        response = manual(
            owner_client,
            line(chart[name], debit=1000),
            line(chart['Modal'], credit=1000),
        )
        assert response.status_code == 409, name


def test_system_accounts_can_be_renamed_but_not_removed(
    owner_client: TestClient,
) -> None:
    chart = accounts(owner_client)
    stock = chart['Persediaan']
    url = f'{LEDGER}accounts/{stock["id"]}'
    body = {'code': '1201', 'name': 'Persediaan Barang', 'type': 'asset'}
    response = owner_client.put(url, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['role'] == 'inventory'
    assert (
        owner_client.put(url, json={**body, 'type': 'expense'}).status_code
        == 409
    )
    assert owner_client.delete(url).status_code == 409

    created = owner_client.post(
        f'{LEDGER}accounts',
        json={'code': '6205', 'name': 'Transport', 'type': 'expense'},
    )
    assert created.status_code == 201, created.text
    transport = created.json()
    manual(
        owner_client,
        line(transport, debit=20000),
        line(chart['Kas Besar'], credit=20000),
    )
    used = f'{LEDGER}accounts/{transport["id"]}'
    assert owner_client.delete(used).status_code == 409
    response = owner_client.put(
        used,
        json={
            'code': '6205',
            'name': 'Transport',
            'type': 'expense',
            'is_active': False,
        },
    )
    assert response.status_code == 200
    duplicate = owner_client.post(
        f'{LEDGER}accounts',
        json={'code': '6205', 'name': 'Bensin', 'type': 'expense'},
    )
    assert duplicate.status_code == 409


def test_account_book_and_trial_balance(owner_client: TestClient) -> None:
    chart = accounts(owner_client)
    manual(
        owner_client,
        line(chart['Bank'], debit=5000000),
        line(chart['Modal'], credit=5000000),
        days_ago=3,
    )
    manual(
        owner_client,
        line(chart['Sewa'], debit=1500000),
        line(chart['Bank'], credit=1500000),
        days_ago=1,
    )
    manual(
        owner_client,
        line(chart['Kas Besar'], debit=300000),
        line(chart['Bank'], credit=300000),
    )
    today = shop_now().date()
    book = owner_client.get(
        f'{LEDGER}accounts/{chart["Bank"]["id"]}/book',
        params={'start': str(today - timedelta(days=1)), 'end': str(today)},
    ).json()
    assert Decimal(book['opening_balance']) == 5000000
    assert [Decimal(x['balance']) for x in book['lines']] == [3500000, 3200000]
    assert Decimal(book['closing_balance']) == 3200000

    trial = owner_client.get(
        f'{LEDGER}trial-balance', params={'on': str(today - timedelta(days=1))}
    ).json()
    rows = {
        row['name']: (Decimal(row['debit']), Decimal(row['credit']))
        for row in trial['rows']
    }
    assert rows == {
        'Bank': (3500000, 0),
        'Modal': (0, 5000000),
        'Sewa': (1500000, 0),
    }
    assert trial['total_debit'] == trial['total_credit']


def test_a_cashier_sees_no_books(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 15."""
    switch_to(owner_client, make_user(session, 'kasir-buku', Role.cashier))
    assert owner_client.get(f'{LEDGER}accounts').status_code == 403
    assert owner_client.get(f'{LEDGER}journal').status_code == 403
