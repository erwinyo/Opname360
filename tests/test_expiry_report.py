"""Slice 6, rule 15: the expiry report, and the Dashboard's count of
expired Batches still in stock."""

from decimal import Decimal

from fastapi.testclient import TestClient
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
