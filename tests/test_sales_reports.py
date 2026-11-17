"""Slice 4, rules 1-4, 7, 8, 12 and 13: Penjualan, Laba Kotor per Jam
and the Dasbor."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pytest

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import Session, select

from .conftest import (
    RECEIPTS,
    give_back,
    make_user,
    method_id,
    new_sku,
    open_shift,
    promote,
    receive,
    sell,
    switch_to,
)

from opname360.models import Receipt, Role, Sku, StockMovement, User
from opname360.services.documents import shop_now
from opname360.services.reports import day_start, latest_activity


SALES = '/api/v1/reports/sales'
HOURLY = '/api/v1/reports/hourly'
FIGURES = (
    'receipt_count',
    'gross_sales',
    'discounts',
    'refunds',
    'net_sales',
    'cogs',
    'gross_profit',
)


@pytest.fixture
def cashier(session: Session) -> User:
    return make_user(session, 'sari', Role.cashier)


@pytest.fixture
def shirt(owner_client: TestClient, session: Session) -> Sku:
    """Rp 80.000 with 10% off; 10 in stock at Rp 50.000."""
    sku = new_sku(owner_client, session, selling_price=80000)
    receive(owner_client, sku, 10, 50000)
    promote(owner_client, 'skus', [sku.id], value=10)
    return sku


@pytest.fixture
def pen(owner_client: TestClient, session: Session) -> Sku:
    """Rp 3.500, nothing in stock; bought before at Rp 2.000."""
    sku = new_sku(owner_client, session, selling_price=3500)
    sku.latest_unit_cost = Decimal(2000)
    session.add(sku)
    session.commit()
    return sku


@pytest.fixture
def till(
    owner_client: TestClient, cashier: User, shirt: Sku, pen: Sku
) -> TestClient:
    switch_to(owner_client, cashier)
    open_shift(owner_client)
    return owner_client


def figures(part: dict) -> tuple:
    return tuple(
        None if part[name] is None else Decimal(part[name]) for name in FIGURES
    )


def sales(
    client: TestClient, start: date, end: date | None = None, **query: object
) -> dict:
    response = client.get(
        SALES, params={'start': str(start), 'end': str(end or start), **query}
    )
    assert response.status_code == 200, response.text
    return response.json()


def at(session: Session, receipt: dict, when: datetime) -> None:
    """Move a Receipt, and its Stock Movements, to `when`."""
    row = session.get(Receipt, receipt['id'])
    assert row is not None
    row.created_at = when
    session.add(row)
    for movement in session.exec(
        select(StockMovement).where(
            StockMovement.document_type == 'receipt',
            StockMovement.document_id == receipt['id'],
        )
    ).all():
        movement.created_at = when
        session.add(movement)
    session.commit()


def void(client: TestClient, receipt: dict) -> None:
    response = client.post(
        f'{RECEIPTS}{receipt["id"]}/void', json={'reason': 'Salah input'}
    )
    assert response.status_code == 200, response.text


def test_net_sales_and_gross_profit_leave_voids_out(
    till: TestClient, owner: User, shirt: Sku, pen: Sku
) -> None:
    """Rules 1 and 3."""
    # 2 shirts: Rp 160.000 less Rp 16.000 off; they cost Rp 100.000.
    sale = sell(till, (shirt, 2)).json()
    void(till, sell(till, (pen, 1)).json())
    # One comes back: Rp 72.000 refunded, Rp 50.000 back in stock.
    assert give_back(till, sale, [(0, 1, 'resellable')]).status_code == 201

    switch_to(till, owner)
    report = sales(till, shop_now().date())
    assert figures(report['total']) == (
        2,
        160000,
        16000,
        72000,
        72000,
        50000,
        22000,
    )


def test_a_return_counts_on_the_day_it_happens(
    till: TestClient, session: Session, owner: User, shirt: Sku
) -> None:
    """Rule 2, with a Damaged Return: its write-off isn't COGS."""
    today = shop_now().date()
    yesterday = today - timedelta(days=1)
    sale = sell(till, (shirt, 2)).json()
    at(session, sale, day_start(yesterday) + timedelta(hours=10))
    assert give_back(till, sale, [(0, 1, 'damaged')]).status_code == 201

    switch_to(till, owner)
    rows = {row['key']: row for row in sales(till, yesterday, today)['rows']}
    assert figures(rows[str(yesterday)]) == (
        1,
        160000,
        16000,
        0,
        144000,
        100000,
        44000,
    )
    assert figures(rows[str(today)]) == (
        1,
        0,
        0,
        72000,
        -72000,
        -50000,
        -22000,
    )


def test_the_hours_add_up_to_the_day(
    till: TestClient, session: Session, owner: User, shirt: Sku, pen: Sku
) -> None:
    """Rules 4 and 7: shop hours, and a Negative Stock cost adjustment
    counted in the hour it was booked."""
    day = shop_now().date() - timedelta(days=3)
    start = day_start(day)
    for minutes, items in [
        # 00:10 in the shop is still the day before in UTC.
        (10, [(shirt, 1)]),
        (9 * 60 + 15, [(pen, 2)]),
        (14 * 60 + 40, [(shirt, 1), (pen, 1)]),
        (23 * 60 + 50, [(shirt, 2)]),
    ]:
        receipt = sell(till, *items).json()
        at(session, receipt, start + timedelta(minutes=minutes))

    switch_to(till, owner)
    # 3 pens went out at Rp 2.000 each; they really cost Rp 2.500.
    receive(till, pen, 10, 2500)
    adjustment = session.exec(
        select(StockMovement).where(
            StockMovement.sku_id == pen.id, StockMovement.quantity == 0
        )
    ).one()
    adjustment.created_at = start + timedelta(hours=10)
    session.add(adjustment)
    session.commit()

    response = till.get(HOURLY, params={'day': str(day)})
    assert response.status_code == 200
    hourly = response.json()
    busy = {
        hour['hour']: hour
        for hour in hourly['hours']
        if hour['receipt_count'] or Decimal(hour['cogs'])
    }
    assert sorted(busy) == [0, 9, 10, 14, 23]
    assert figures(busy[10]) == (0, 0, 0, 0, 0, 1500, -1500)
    summed = tuple(
        sum(column)
        for column in zip(*map(figures, hourly['hours']), strict=True)
    )
    [row] = sales(till, day)['rows']
    assert summed == figures(row) == figures(hourly)
    assert figures(row) == (4, 330500, 32000, 0, 298500, 207500, 91000)


def test_penjualan_by_cashier_method_and_category_down_to_receipts(
    till: TestClient,
    owner: User,
    cashier: User,
    shirt: Sku,
    pen: Sku,
) -> None:
    qris = method_id(till, 'QRIS')
    # Rp 72.000 + Rp 7.000, paid partly in cash and partly by QRIS.
    first = sell(
        till,
        (shirt, 1),
        (pen, 2),
        payments=[
            {'payment_method_id': method_id(till), 'amount': 50000},
            {'payment_method_id': qris, 'amount': 29000, 'confirmed': True},
        ],
    ).json()
    switch_to(till, owner)
    second = sell(till, (pen, 1)).json()
    today = shop_now().date()

    def rows(group_by: str) -> dict:
        report = sales(till, today, group_by=group_by)
        assert report['total']['net_sales'] == 82500
        return {
            row['label']: (row['net_sales'], row['gross_profit'])
            for row in report['rows']
        }

    assert rows('cashier') == {
        cashier.full_name: (79000, None),
        owner.full_name: (3500, None),
    }
    assert rows('payment_method') == {
        'Tunai': (53500, None),
        'QRIS': (29000, None),
    }
    shirts = shirt.product.sub_category.category
    pens = pen.product.sub_category.category
    assert rows('category') == {
        shirts.name: (72000, '22000.0000'),
        pens.name: (10500, '4500.0000'),
    }

    def receipts(**query: object) -> list:
        response = till.get(
            f'{SALES}/receipts',
            params={'start': str(today), 'end': str(today), **query},
        )
        assert response.status_code == 200, response.text
        return [
            (item['id'], item['amount']) for item in response.json()['items']
        ]

    assert receipts(category_id=pens.id) == [
        (second['id'], 3500),
        (first['id'], 7000),
    ]
    assert receipts(payment_method_id=qris) == [(first['id'], 29000)]
    assert receipts(cashier_id=cashier.id) == [(first['id'], 79000)]


def test_the_excel_files_have_the_numbers_on_screen(
    till: TestClient, session: Session, owner: User, shirt: Sku, pen: Sku
) -> None:
    """Rule 12."""
    sale = sell(till, (shirt, 1), (pen, 3)).json()
    noon = day_start(shop_now().date()) + timedelta(hours=12, minutes=5)
    at(session, sale, noon)
    switch_to(till, owner)
    today = str(shop_now().date())

    def sheet(path: str, **query: object) -> list[list]:
        response = till.get(path, params=query)
        assert response.status_code == 200, response.text
        book = load_workbook(BytesIO(response.content)).active
        assert book is not None
        # Below the title, the subtitle, a blank row and the header.
        return [[cell.value for cell in row] for row in book.iter_rows()][4:]

    def numbers(part: dict) -> list:
        return [
            '' if part[name] is None else round(Decimal(part[name]))
            for name in FIGURES
        ]

    query = {'start': today, 'end': today, 'group_by': 'category'}
    report = sales(till, shop_now().date(), group_by='category')
    lines = sheet(f'{SALES}/excel', **query)
    assert lines == [
        *([row['label'], *numbers(row)] for row in report['rows']),
        ['Total', *numbers(report['total'])],
    ]

    hourly = till.get(HOURLY, params={'day': today}).json()
    lines = sheet(f'{HOURLY}/excel', day=today)
    assert ['12.00-13.00', *numbers(hourly['hours'][12])] in lines
    assert lines[-1] == ['Total', *numbers(hourly)]


def test_the_dashboard_hears_of_every_sale_and_void(
    till: TestClient, session: Session, owner: User, shirt: Sku
) -> None:
    """Rule 8: what the live stream watches grows with every sale and
    Void, and the dashboard shows today as it is."""
    before = latest_activity(session)
    voided = sell(till, (shirt, 1)).json()
    after_sale = latest_activity(session)
    assert after_sale > before
    void(till, voided)
    assert latest_activity(session) > after_sale
    sell(till, (shirt, 2))

    switch_to(till, owner)
    today = till.get('/api/v1/reports/dashboard').json()['today']
    assert (today['receipt_count'], today['net_sales']) == (1, 144000)
    assert today['day'] == str(shop_now().date())


def test_a_cashier_sees_no_sales_report(till: TestClient) -> None:
    """Rule 13."""
    today = str(shop_now().date())
    for path, query in [
        (SALES, {'start': today, 'end': today}),
        (f'{SALES}/receipts', {'start': today, 'end': today}),
        (HOURLY, {'day': today}),
        ('/api/v1/reports/dashboard', {}),
        ('/api/v1/reports/live', {}),
    ]:
        assert till.get(path, params=query).status_code == 403, path
