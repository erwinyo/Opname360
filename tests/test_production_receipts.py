from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_user, new_sku, receipt_line, sign_in, stock_of

from opname360.models import Role


PRODUCTION = '/api/v1/production-receipts/'


def new_production(
    client: TestClient, lines: list[dict], *, complete: bool = True
) -> dict:
    response = client.post(
        PRODUCTION, json={'produced_on': '2026-11-15', 'lines': lines}
    )
    assert response.status_code == 201, response.text
    receipt = response.json()
    if complete:
        response = client.post(f'{PRODUCTION}{receipt["id"]}/complete')
        assert response.status_code == 200, response.text
        receipt = response.json()
    return receipt


def test_finished_goods_enter_stock_at_the_cost_typed_in(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)

    draft = new_production(
        owner_client, [receipt_line(sku.id, 20, 45000)], complete=False
    )
    assert stock_of(owner_client, sku.id) == (0, 0)

    completed = owner_client.post(f'{PRODUCTION}{draft["id"]}/complete').json()

    assert completed['status'] == 'completed'
    assert completed['number'].startswith('HP-')
    assert Decimal(completed['total_cost']) == 900000
    assert stock_of(owner_client, sku.id) == (20, 900000)
    card = owner_client.get(f'/api/v1/stock/skus/{sku.id}/card').json()
    assert card['items'][0]['reason'] == 'production_receipt'
    assert card['items'][0]['document_number'] == completed['number']


def test_a_completed_production_receipt_is_immutable(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    receipt = new_production(owner_client, [receipt_line(sku.id, 1, 100)])
    url = f'{PRODUCTION}{receipt["id"]}'

    change = owner_client.put(
        url, json={'produced_on': '2026-11-15', 'lines': []}
    )

    assert change.status_code == 409
    assert owner_client.delete(url).status_code == 409


def test_production_receipts_are_listed_newest_first(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    first = new_production(owner_client, [receipt_line(sku.id, 1, 100)])
    draft = new_production(
        owner_client, [receipt_line(sku.id, 2, 100)], complete=False
    )

    page = owner_client.get(PRODUCTION).json()

    assert [item['id'] for item in page['items']] == [draft['id'], first['id']]
    assert page['items'][1]['line_count'] == 1


def test_a_cashier_cannot_record_production(
    client: TestClient, session: Session
) -> None:
    make_user(session, 'kasir', Role.cashier)
    sign_in(client, 'kasir')

    assert client.get(PRODUCTION).status_code == 403
