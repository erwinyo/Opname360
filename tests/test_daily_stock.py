"""Slice 4, rules 5-7, 12 and 13: Laporan Stok Harian."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import Session, select

from .conftest import (
    make_user,
    new_product,
    new_sku,
    open_shift,
    receive,
    sell,
    sku_row,
    switch_to,
)

from opname360.models import Role, Sku, StockMovement
from opname360.services.documents import shop_now
from opname360.services.reports import day_start


REPORT = '/api/v1/reports/daily-stock'


def backdate(session: Session, sku: Sku, when: datetime) -> None:
    """Move every Stock Movement of `sku` so far to `when`."""
    movements = session.exec(
        select(StockMovement).where(StockMovement.sku_id == sku.id)
    ).all()
    for movement in movements:
        movement.created_at = when
        session.add(movement)
    session.commit()


def daily(client: TestClient, day: date, **query: object) -> dict:
    response = client.get(REPORT, params={'day': str(day), **query})
    assert response.status_code == 200, response.text
    return response.json()


def flow(part: dict) -> list[Decimal]:
    return [
        Decimal(part[name])
        for name in (
            'opening',
            'quantity_in',
            'quantity_out',
            'closing',
            'closing_value',
        )
    ]


def test_opening_in_out_and_closing_add_up_and_carry_over(
    owner_client: TestClient, session: Session
) -> None:
    """Rules 5 and 6, for SKUs and every subtotal."""
    shirt = new_sku(owner_client, session, selling_price=80000)
    receive(owner_client, shirt, 10, 50000)
    today = shop_now().date()
    yesterday = today - timedelta(days=1)
    backdate(session, shirt, day_start(yesterday) + timedelta(hours=9))
    # Today: 5 more at Rp 56.000 (average Rp 52.000), then 2 sold.
    receive(owner_client, shirt, 5, 56000)
    sub_category_id = shirt.product.sub_category_id
    trousers = new_product(
        owner_client,
        sub_category_id,
        'Celana Biru SD',
        [sku_row(size='12', selling_price=90000)],
    )
    trousers_sku = session.get(Sku, trousers['skus'][0]['id'])
    assert trousers_sku is not None
    receive(owner_client, trousers_sku, 4, 30000)
    open_shift(owner_client)
    assert sell(owner_client, (shirt, 2)).status_code == 201

    category_id = shirt.product.sub_category.category_id
    before = daily(owner_client, yesterday, category_id=category_id)
    after = daily(owner_client, today, category_id=category_id)

    [category] = before['categories']
    [row] = category['sub_categories'][0]['rows']
    assert flow(row) == [0, 10, 0, 10, 500000]

    [category] = after['categories']
    [sub_category] = category['sub_categories']
    rows = {row['sku_id']: row for row in sub_category['rows']}
    assert flow(rows[shirt.id]) == [10, 5, 2, 13, 13 * 52000]
    assert flow(rows[trousers_sku.id]) == [0, 4, 0, 4, 120000]
    # The shirt's closing value is its Stock Value now.
    card = owner_client.get(f'/api/v1/stock/skus/{shirt.id}/card').json()
    assert rows[shirt.id]['closing_value'] == card['sku']['value']
    for part in (sub_category, category, after):
        opening, quantity_in, quantity_out, closing, _ = flow(part)
        assert opening + quantity_in - quantity_out == closing
    assert flow(after) == [10, 9, 2, 17, 13 * 52000 + 120000]
    # Yesterday's closing is today's opening.
    assert flow(before)[3] == flow(after)[0]


def test_a_day_is_the_shops_day_not_utc(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 7: 00:30 in the shop is still the previous day in UTC."""
    pen = new_sku(owner_client, session, selling_price=3500)
    receive(owner_client, pen, 3, 2000)
    day = shop_now().date() - timedelta(days=2)
    half_past_midnight = day_start(day) + timedelta(minutes=30)
    assert half_past_midnight.astimezone(UTC).date() == day - timedelta(1)
    backdate(session, pen, half_past_midnight)
    category_id = pen.product.sub_category.category_id

    report = daily(owner_client, day, category_id=category_id)
    [row] = report['categories'][0]['sub_categories'][0]['rows']
    assert flow(row) == [0, 3, 0, 3, 6000]
    earlier = daily(owner_client, day - timedelta(1), category_id=category_id)
    assert earlier['categories'] == []


def test_the_excel_file_has_the_numbers_on_screen(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 12."""
    cloth = new_sku(owner_client, session, selling_price=25000)
    receive(owner_client, cloth, 12.5, 10001)
    today = shop_now().date()
    category_id = cloth.product.sub_category.category_id
    report = daily(owner_client, today, category_id=category_id)
    row = report['categories'][0]['sub_categories'][0]['rows'][0]

    response = owner_client.get(
        f'{REPORT}/excel',
        params={'day': str(today), 'category_id': category_id},
    )
    assert response.status_code == 200
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet is not None
    cells = [[cell.value for cell in line] for line in sheet.iter_rows()]
    [line] = [line for line in cells if line[3] == cloth.code]
    assert line[5:] == [
        Decimal(row['opening']),
        Decimal(row['quantity_in']),
        Decimal(row['quantity_out']),
        Decimal(row['closing']),
        # Rp 125.012,5 shows as Rp 125.013 on screen (Math.round).
        125013,
    ]
    assert row['closing_value'] == '125012.5000'
    assert cells[-1][2] == 'Total'
    assert cells[-1][-1] == 125013


def test_a_cashier_sees_no_report(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 13."""
    switch_to(owner_client, make_user(session, 'kasir-laporan', Role.cashier))
    response = owner_client.get(REPORT, params={'day': '2026-11-17'})
    assert response.status_code == 403
