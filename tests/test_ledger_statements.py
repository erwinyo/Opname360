"""Slice 5, rules 12-14: Laba Rugi, Neraca and closing a period."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import Session, select

from .conftest import (
    close_shift,
    give_back,
    make_user,
    new_receipt,
    new_sku,
    new_supplier,
    open_shift,
    promote,
    receipt_line,
    sell,
    switch_to,
)

from opname360.models import Account, Role
from opname360.services.documents import shop_now


LEDGER = '/api/v1/ledger/'


def account(session: Session, name: str) -> int:
    found = session.exec(select(Account).where(Account.name == name)).one()
    assert found.id is not None
    return found.id


def amounts(lines: list[dict]) -> dict[str, Decimal]:
    return {line['name']: Decimal(line['amount']) for line in lines}


def test_profit_and_loss(owner_client: TestClient, session: Session) -> None:
    """Rule 14: net sales, COGS, gross profit, expenses by account, other
    income, net profit."""
    shirt = new_sku(owner_client, session, selling_price=80000)
    supplier = new_supplier(owner_client)
    new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 10, 50000)],
        payment_status='owed',
    )
    promote(owner_client, 'skus', [shirt.id], value=10)
    shift = open_shift(owner_client, 100000)
    sale = sell(owner_client, (shirt, 2)).json()
    give_back(owner_client, sale, [(0, 1, 'damaged')])
    owner_client.post(
        '/api/v1/cash/outs',
        json={
            'paid_on': str(shop_now().date()),
            'paid_from_account_id': account(session, 'Kas Besar'),
            'expense_account_id': account(session, 'Listrik dan Air'),
            'amount': 100000,
            'description': 'Token listrik',
        },
    )
    # Expected 100.000 + 144.000 - 72.000; 2.000 more is in the drawer.
    close_shift(owner_client, shift['id'], 174000)

    today = str(shop_now().date())
    report = owner_client.get(
        f'{LEDGER}profit-and-loss', params={'start': today, 'end': today}
    ).json()
    assert amounts(report['sales']) == {
        'Penjualan': 160000,
        'Diskon Penjualan': -16000,
        'Retur Penjualan': -72000,
    }
    assert [line['name'] for line in report['sales']] == [
        'Penjualan',
        'Diskon Penjualan',
        'Retur Penjualan',
    ]
    assert Decimal(report['net_sales']) == 72000
    assert amounts(report['cogs']) == {'Harga Pokok Penjualan': 50000}
    assert Decimal(report['gross_profit']) == 22000
    assert amounts(report['expenses']) == {
        'Barang Rusak': 50000,
        'Listrik dan Air': 100000,
    }
    assert amounts(report['other_income']) == {'Selisih Lebih Kas': 2000}
    assert Decimal(report['net_profit']) == 22000 - 150000 + 2000

    response = owner_client.get(
        f'{LEDGER}profit-and-loss/excel', params={'start': today, 'end': today}
    )
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet is not None
    last = [cell.value for cell in list(sheet.iter_rows())[-1]]
    assert last == ['Laba bersih', -126000]


def test_the_balance_sheet_balances_across_years(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 13: earlier years' profit is Laba Ditahan, this year's Laba
    Tahun Berjalan, with no closing entry."""
    today = shop_now().date()
    last_year = date(today.year - 1, 12, 15)

    def manual(day: date, debit: str, credit: str, amount: int) -> None:
        response = owner_client.post(
            f'{LEDGER}journal',
            json={
                'entry_date': str(day),
                'description': 'Contoh',
                'lines': [
                    {'account_id': account(session, debit), 'debit': amount},
                    {'account_id': account(session, credit), 'credit': amount},
                ],
            },
        )
        assert response.status_code == 201, response.text

    manual(last_year, 'Bank', 'Modal', 10000000)
    manual(last_year, 'Bank', 'Pendapatan Lain', 500000)
    manual(today, 'Sewa', 'Bank', 1500000)
    manual(today, 'Prive', 'Bank', 250000)

    def sheet(on: date) -> dict:
        response = owner_client.get(
            f'{LEDGER}balance-sheet', params={'on': str(on)}
        )
        assert response.status_code == 200, response.text
        report = response.json()
        assert report['total_assets'] == report['total_liabilities_and_equity']
        return report

    year_end = sheet(date(today.year - 1, 12, 31))
    assert amounts(year_end['assets']) == {'Bank': 10500000}
    assert amounts(year_end['equity']) == {
        'Modal': 10000000,
        'Laba Tahun Berjalan': 500000,
    }
    now = sheet(today)
    assert amounts(now['assets']) == {'Bank': 8750000}
    assert amounts(now['equity']) == {
        'Modal': 10000000,
        'Prive': -250000,
        'Laba Ditahan': 500000,
        'Laba Tahun Berjalan': -1500000,
    }

    response = owner_client.get(
        f'{LEDGER}balance-sheet/excel', params={'on': str(today)}
    )
    book = load_workbook(BytesIO(response.content)).active
    assert book is not None
    last = [cell.value for cell in list(book.iter_rows())[-1]]
    assert last == [
        'Total aset',
        8750000,
        'Total kewajiban dan ekuitas',
        8750000,
    ]


def test_nothing_is_posted_on_or_before_the_lock_date(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 12: only the Owner moves it, and never to today."""
    today = shop_now().date()
    yesterday = today - timedelta(days=1)
    url = f'{LEDGER}lock-date'
    assert (
        owner_client.put(url, json={'lock_date': str(today)}).status_code
        == 409
    )
    response = owner_client.put(url, json={'lock_date': str(yesterday)})
    assert response.status_code == 200, response.text
    assert owner_client.get(url).json() == {'lock_date': str(yesterday)}

    def entry(day: date):
        return owner_client.post(
            f'{LEDGER}journal',
            json={
                'entry_date': str(day),
                'description': 'Setoran modal',
                'lines': [
                    {'account_id': account(session, 'Bank'), 'debit': 1000},
                    {'account_id': account(session, 'Modal'), 'credit': 1000},
                ],
            },
        )

    closed = entry(yesterday)
    assert closed.status_code == 409
    assert 'ditutup' in closed.json()['detail']
    assert entry(today).status_code == 201
    late = owner_client.post(
        '/api/v1/cash/outs',
        json={
            'paid_on': str(yesterday),
            'paid_from_account_id': account(session, 'Kas Besar'),
            'expense_account_id': account(session, 'Biaya Lain'),
            'amount': 1000,
            'description': 'Parkir',
        },
    )
    assert late.status_code == 409

    switch_to(owner_client, make_user(session, 'admin-tutup', Role.admin))
    assert owner_client.get(url).status_code == 200
    assert owner_client.put(url, json={'lock_date': None}).status_code == 403
