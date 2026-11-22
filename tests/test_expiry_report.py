"""Slice 6, rule 15: the expiry report, and the Dashboard's count of
expired Batches still in stock."""

from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import Session

from .conftest import open_shift, sell
from .test_batch_selling import expire, stocked


EXPIRY = '/api/v1/reports/expiry'


def test_batches_in_stock_that_expired_or_expire_soon(
    owner_client: TestClient, session: Session
) -> None:
    pills = stocked(
        owner_client,
        session,
        ('GONE', 2, 5),
        ('OLD', 4, 8),
        ('SOON', 3, 10),
        ('MID', 2, 45),
        ('LATE', 5, 200),
    )
    open_shift(owner_client)
    # GONE expires first, so the sale empties it.
    assert sell(owner_client, (pills, 2)).status_code == 201
    expire(session, pills, 'GONE')
    expire(session, pills, 'OLD')

    def report(days: int) -> dict:
        response = owner_client.get(EXPIRY, params={'days': days})
        assert response.status_code == 200, response.text
        return response.json()

    month = report(30)
    assert [
        (row['batch_number'], row['expired']) for row in month['rows']
    ] == [
        ('OLD', True),
        ('SOON', False),
    ]
    old = month['rows'][0]
    assert Decimal(old['quantity']) == 4
    # Every unit came in at Rp 20.000, so that is the average cost.
    assert Decimal(old['value']) == 80000
    assert Decimal(month['expired_value']) == 80000
    assert Decimal(month['expiring_value']) == 60000
    assert [row['batch_number'] for row in report(60)['rows']] == [
        'OLD',
        'SOON',
        'MID',
    ]

    dashboard = owner_client.get('/api/v1/reports/dashboard').json()
    assert dashboard['attention']['expired_batches'] == 1

    # The Excel file has the numbers on screen.
    response = owner_client.get(f'{EXPIRY}/excel', params={'days': 30})
    assert response.status_code == 200, response.text
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet is not None
    lines = [[cell.value for cell in row] for row in sheet.iter_rows()][4:]
    assert [(line[2], line[4], line[5], line[7]) for line in lines[:2]] == [
        ('OLD', 'lewat 1 hari', 4, 80000),
        ('SOON', '10 hari lagi', 3, 60000),
    ]
    assert [(line[0], line[7]) for line in lines[2:]] == [
        ('Total sudah kedaluwarsa', 80000),
        ('Total kedaluwarsa dalam 30 hari', 60000),
    ]
