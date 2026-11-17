"""Slice 4: Selisih Opname, and the dashboard's attention list."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlmodel import Session

from .conftest import (
    OPNAMES,
    RECEIPTS,
    close_shift,
    make_user,
    new_sku,
    open_shift,
    receive,
    sell,
)
from .test_opname_approval import approve, resolve, reviewed

from opname360.models import Role, User
from opname360.services.documents import shop_now


VARIANCES = '/api/v1/reports/variances'


def test_selisih_opname_by_sku_reason_and_resolution(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    shirt = new_sku(owner_client, session)
    hat = new_sku(owner_client, session)
    tie = new_sku(owner_client, session)
    pen = new_sku(owner_client, session)
    receive(owner_client, shirt, 5, 1000)
    receive(owner_client, hat, 5, 2000)
    receive(owner_client, tie, 4, 500)
    receive(owner_client, pen, 4, 100)
    culprit = make_user(session, 'joko', Role.cashier)
    # 2 shirts lost and charged, 1 tie damaged, 1 hat too many.
    opname, lines = reviewed(
        owner_client, session, owner, {shirt.id: 3, hat.id: 6, tie.id: 3}
    )
    resolve(
        owner_client,
        opname,
        lines[shirt.id],
        shortage_reason='lost',
        resolution='employee_charge',
        charged_user_id=culprit.id,
    )
    resolve(owner_client, opname, lines[tie.id], shortage_reason='damaged')
    assert approve(owner_client, opname).status_code == 200
    # A reversed session counts for nothing.
    undone, undone_lines = reviewed(owner_client, session, owner, {pen.id: 1})
    resolve(owner_client, undone, undone_lines[pen.id], shortage_reason='lost')
    assert approve(owner_client, undone).status_code == 200
    response = owner_client.post(
        f'{OPNAMES}{undone["id"]}/reverse', json={'reason': 'Salah rak'}
    )
    assert response.status_code == 200, response.text

    today = str(shop_now().date())

    def report(group_by: str, start: str = today) -> dict:
        response = owner_client.get(
            VARIANCES,
            params={'start': start, 'end': today, 'group_by': group_by},
        )
        assert response.status_code == 200, response.text
        return response.json()

    def figures(part: dict) -> tuple:
        return tuple(
            Decimal(part[name])
            for name in (
                'shortage_quantity',
                'shortage_value',
                'surplus_quantity',
                'surplus_value',
            )
        )

    by_sku = report('sku')
    assert {row['key']: figures(row) for row in by_sku['rows']} == {
        str(shirt.id): (2, 2000, 0, 0),
        str(tie.id): (1, 500, 0, 0),
        str(hat.id): (0, 0, 1, 2000),
    }
    assert figures(by_sku['total']) == (3, 2500, 1, 2000)
    assert Decimal(by_sku['total']['net_value']) == -500
    assert {
        row['label']: figures(row) for row in report('reason')['rows']
    } == {
        'Hilang': (2, 2000, 0, 0),
        'Rusak': (1, 500, 0, 0),
        'Selisih lebih': (0, 0, 1, 2000),
    }
    assert {
        row['label']: figures(row) for row in report('resolution')['rows']
    } == {
        'Ganti rugi karyawan': (2, 2000, 0, 0),
        'Kerugian perusahaan': (1, 500, 0, 0),
        'Selisih lebih': (0, 0, 1, 2000),
    }

    # Rule 12: the Excel file has the same numbers.
    response = owner_client.get(
        f'{VARIANCES}/excel',
        params={'start': today, 'end': today, 'group_by': 'reason'},
    )
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet is not None
    cells = [[cell.value for cell in row] for row in sheet.iter_rows()]
    assert cells[-1] == ['Total', None, 3, 3, 2500, 1, 2000, -500]


def test_the_dashboard_lists_what_needs_attention(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    pen = new_sku(owner_client, session, selling_price=3500)
    shirt = new_sku(owner_client, session, selling_price=80000)
    receive(owner_client, shirt, 5, 50000)
    shift = open_shift(owner_client, 100000)
    # Sold before it was received: Negative Stock.
    assert sell(owner_client, (pen, 2)).status_code == 201
    mistake = sell(owner_client, (shirt, 1)).json()
    response = owner_client.post(
        f'{RECEIPTS}{mistake["id"]}/void', json={'reason': 'Salah ukuran'}
    )
    assert response.status_code == 200
    # Rp 7.000 should be in the drawer on top of the float; 5.000 is.
    assert close_shift(owner_client, shift['id'], 105000).status_code == 200
    reviewed(owner_client, session, owner, {shirt.id: 4})

    attention = owner_client.get('/api/v1/reports/dashboard').json()[
        'attention'
    ]
    assert attention['negative_stock'] == 1
    assert [
        (void['number'], void['reason'], void['total'])
        for void in attention['voids_today']
    ] == [(mistake['number'], 'Salah ukuran', 80000)]
    assert attention['opnames_waiting'] == 1
    assert attention['shifts_waiting'] == 1


def test_an_earlier_period_has_no_variances(
    owner_client: TestClient,
) -> None:
    yesterday = str(shop_now().date() - timedelta(days=1))
    response = owner_client.get(
        VARIANCES, params={'start': yesterday, 'end': yesterday}
    )
    assert response.status_code == 200
    assert response.json()['rows'] == []
