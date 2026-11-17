"""Slice 4, rules 9, 10, 12 and 13: Fast Moving and Kontribusi Omzet."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import Session

from .conftest import (
    give_back,
    make_user,
    new_sku,
    open_shift,
    receive,
    sell,
    switch_to,
)
from .test_sales_reports import at

from opname360.models import Role
from opname360.services.documents import shop_now
from opname360.services.reports import day_start


FAST = '/api/v1/reports/fast-moving'
ABC = '/api/v1/reports/abc'


@pytest.fixture
def till(owner_client: TestClient) -> TestClient:
    """The Owner selling."""
    open_shift(owner_client)
    return owner_client


def report(client: TestClient, path: str, start: date, **query: object):
    response = client.get(
        path,
        params={'start': str(start), 'end': str(shop_now().date()), **query},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_fast_moving_ranks_by_units_sold_less_returned(
    till: TestClient, session: Session
) -> None:
    """Rule 9: over the last 30 days unless another period is chosen."""
    pen = new_sku(till, session, selling_price=3500)
    ruler = new_sku(till, session, selling_price=5000)
    book = new_sku(till, session, selling_price=7000)
    receive(till, pen, 20, 2000)
    sale = sell(till, (pen, 5), (ruler, 4)).json()
    pen_line = next(
        i for i, line in enumerate(sale['lines']) if line['sku_id'] == pen.id
    )
    assert (
        give_back(till, sale, [(pen_line, 2, 'resellable')]).status_code == 201
    )
    long_ago = sell(till, (book, 9)).json()
    today = shop_now().date()
    at(session, long_ago, day_start(today - timedelta(days=31)))
    sell(till, (book, 1))

    last_30_days = report(till, FAST, today - timedelta(days=29))['rows']
    assert [
        (row['sku_id'], Decimal(row['units_sold']), row['net_sales'])
        for row in last_30_days
    ] == [(ruler.id, 4, 20000), (pen.id, 3, 10500), (book.id, 1, 7000)]
    assert Decimal(last_30_days[1]['stock']) == 17

    longer = report(till, FAST, today - timedelta(days=40))['rows']
    assert [row['sku_id'] for row in longer] == [book.id, ruler.id, pen.id]


def test_abc_class_a_runs_to_80_percent_then_b_to_95(
    till: TestClient, session: Session
) -> None:
    """Rule 10: the SKU crossing a line stays in the class below it; SKUs
    with no sales are C."""
    x, y, z, w, unsold = (
        new_sku(till, session, selling_price=price)
        for price in (70000, 20000, 6000, 4000, 1000)
    )
    sell(till, (x, 1), (y, 1), (z, 1), (w, 1))

    abc = report(till, ABC, shop_now().date())
    assert [
        (row['sku_id'], row['share'], row['running_share'], row['abc_class'])
        for row in abc['rows']
    ] == [
        (x.id, '0.7000', '0.7000', 'A'),
        # Crosses 80% but started below it: still A.
        (y.id, '0.2000', '0.9000', 'A'),
        (z.id, '0.0600', '0.9600', 'B'),
        (w.id, '0.0400', '1.0000', 'C'),
        (unsold.id, '0.0000', '1.0000', 'C'),
    ]
    assert [
        (c['abc_class'], c['sku_count'], c['net_sales'], c['share'])
        for c in abc['classes']
    ] == [
        ('A', 2, 90000, '0.9000'),
        ('B', 1, 6000, '0.0600'),
        ('C', 2, 4000, '0.0400'),
    ]


def test_the_excel_files_have_the_numbers_on_screen(
    till: TestClient, session: Session
) -> None:
    """Rule 12."""
    pen = new_sku(till, session, selling_price=3500)
    ruler = new_sku(till, session, selling_price=5000)
    sell(till, (pen, 3), (ruler, 1))
    today = shop_now().date()

    def sheet(path: str) -> list[list]:
        response = till.get(
            f'{path}/excel', params={'start': str(today), 'end': str(today)}
        )
        assert response.status_code == 200, response.text
        book = load_workbook(BytesIO(response.content)).active
        assert book is not None
        return [[cell.value for cell in row] for row in book.iter_rows()][4:]

    fast = report(till, FAST, today)['rows']
    assert [(line[2], line[4], line[5]) for line in sheet(FAST)] == [
        (row['code'], Decimal(row['units_sold']), row['net_sales'])
        for row in fast
    ]
    abc = report(till, ABC, today)
    lines = sheet(ABC)
    assert [
        (line[0], line[2], line[4], line[5])
        for line in lines[: len(abc['rows'])]
    ] == [
        (
            row['abc_class'],
            row['code'],
            row['net_sales'],
            float(row['share']),
        )
        for row in abc['rows']
    ]
    assert lines[-1][4] == abc['net_sales'] == 15500


def test_a_cashier_sees_neither(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 13."""
    switch_to(owner_client, make_user(session, 'kasir-abc', Role.cashier))
    today = str(shop_now().date())
    for path in (FAST, ABC):
        response = owner_client.get(
            path, params={'start': today, 'end': today}
        )
        assert response.status_code == 403
