"""Slice 3, rules 7 and 18: Promotions."""

from datetime import timedelta

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import (
    NOW,
    PROMOTIONS,
    RECEIPTS,
    cart,
    make_user,
    new_category,
    new_product,
    open_shift,
    promote,
    sell,
    sku_row,
    switch_to,
)

from opname360.models import Role, Sku, User


@pytest.fixture
def uniforms(owner_client: TestClient, session: Session) -> dict:
    """Category Seragam: a Rp 80.000 shirt and a Rp 20.000 tie."""
    category = new_category(owner_client, 'Seragam', ('Kemeja', 'Dasi'))
    shirt_sub, tie_sub = category['sub_categories']
    shirt = new_product(
        owner_client,
        shirt_sub['id'],
        'Kemeja Putih',
        [sku_row(selling_price=80000)],
    )
    tie = new_product(
        owner_client, tie_sub['id'], 'Dasi SD', [sku_row(selling_price=20000)]
    )
    return {
        'category': category,
        'shirt': session.get(Sku, shirt['skus'][0]['id']),
        'tie': session.get(Sku, tie['skus'][0]['id']),
    }


def quote(client: TestClient, *items: tuple[Sku, float]) -> dict:
    return client.post(f'{RECEIPTS}quote', json={'lines': cart(*items)}).json()


# Rule 7


def test_the_biggest_running_discount_wins_and_they_never_add_up(
    owner_client: TestClient, uniforms: dict
) -> None:
    shirt, tie = uniforms['shirt'], uniforms['tie']
    promote(
        owner_client,
        'categories',
        [uniforms['category']['id']],
        value=10,
        name='Seragam 10%',
    )
    promote(
        owner_client,
        'skus',
        [shirt.id],
        value=5000,
        discount_kind='fixed',
        name='Kemeja hemat',
    )

    lines = {
        line['sku_id']: line
        for line in quote(owner_client, (shirt, 2), (tie, 1))['lines']
    }
    # 10% of Rp 80.000 is more than Rp 5.000 off.
    assert (
        lines[shirt.id]['promotion_name'],
        lines[shirt.id]['discount'],
    ) == (
        'Seragam 10%',
        16000,
    )
    assert lines[shirt.id]['line_total'] == 144000
    assert (lines[tie.id]['promotion_name'], lines[tie.id]['discount']) == (
        'Seragam 10%',
        2000,
    )

    # Rp 25.000 off a Rp 20.000 tie makes it free, not less.
    promote(
        owner_client,
        'sub_categories',
        [uniforms['category']['sub_categories'][1]['id']],
        value=25000,
        discount_kind='fixed',
        name='Dasi gratis',
    )
    tie_line = quote(owner_client, (tie, 1))['lines'][0]
    assert (tie_line['promotion_name'], tie_line['line_total']) == (
        'Dasi gratis',
        0,
    )


def test_a_promotion_applies_only_inside_its_period(
    owner_client: TestClient, uniforms: dict
) -> None:
    shirt = uniforms['shirt']
    product_id = shirt.product_id
    promote(
        owner_client,
        'products',
        [product_id],
        value=50,
        starts=timedelta(days=1),
        ends=timedelta(days=2),
    )
    promote(
        owner_client,
        'products',
        [product_id],
        value=40,
        starts=timedelta(days=-3),
        ends=timedelta(days=-1),
    )
    assert quote(owner_client, (shirt, 1))['discount_total'] == 0
    promote(owner_client, 'products', [product_id], value=20)
    assert quote(owner_client, (shirt, 1))['discount_total'] == 16000


def test_the_receipt_keeps_the_promotion_and_discount(
    owner_client: TestClient, uniforms: dict
) -> None:
    shirt, tie = uniforms['shirt'], uniforms['tie']
    promote(owner_client, 'skus', [shirt.id], value=25, name='Akhir tahun')
    promote(owner_client, 'skus', [tie.id], value=20000, discount_kind='fixed')
    open_shift(owner_client)
    receipt = sell(owner_client, (shirt, 1)).json()
    assert receipt['subtotal'] == 80000
    assert receipt['discount_total'] == 20000
    assert receipt['total'] == 60000
    assert receipt['lines'][0]['promotion_name'] == 'Akhir tahun'
    # Free: nothing to pay.
    free = sell(owner_client, (tie, 1), payments=[])
    assert free.status_code == 201, free.text
    assert (free.json()['total'], free.json()['payments']) == (0, [])


# Rule 18


def test_a_used_promotion_can_only_be_ended_early(
    owner_client: TestClient, session: Session, uniforms: dict
) -> None:
    shirt = uniforms['shirt']
    used = promote(owner_client, 'skus', [shirt.id], value=10)
    unused = promote(
        owner_client,
        'skus',
        [shirt.id],
        value=5,
        starts=timedelta(days=1),
        ends=timedelta(days=2),
    )
    open_shift(owner_client)
    sell(owner_client, (shirt, 1))

    body = {
        'name': 'Ganti',
        'discount_kind': 'percentage',
        'value': 15,
        'target_kind': 'skus',
        'target_ids': [shirt.id],
        'starts_at': NOW.isoformat(),
        'ends_at': (NOW + timedelta(days=1)).isoformat(),
    }
    response = owner_client.put(f'{PROMOTIONS}{used["id"]}', json=body)
    assert response.status_code == 409
    assert 'sudah dipakai' in response.json()['detail']
    response = owner_client.put(f'{PROMOTIONS}{unused["id"]}', json=body)
    assert response.status_code == 200
    assert response.json()['value'] == 15

    for promotion in (used, unused):
        response = owner_client.post(f'{PROMOTIONS}{promotion["id"]}/end')
        assert response.json()['status'] == 'ended'
    assert quote(owner_client, (shirt, 1))['discount_total'] == 0
    assert (
        owner_client.post(f'{PROMOTIONS}{used["id"]}/end').status_code == 409
    )
    ended = owner_client.get(PROMOTIONS, params={'status': 'ended'}).json()
    assert ended['total'] == 2


def test_promotions_are_set_by_the_owner_or_an_admin(
    owner_client: TestClient, session: Session, uniforms: dict
) -> None:
    shirt = uniforms['shirt']
    admin = make_user(session, 'admin', Role.admin)
    switch_to(owner_client, admin)
    promotion = promote(owner_client, 'skus', [shirt.id], value=10)
    assert promotion['created_by_name'] == 'Admin'
    assert promotion['targets'][0]['label'] == 'Kemeja Putih (10)'

    cashier: User = make_user(session, 'ani', Role.cashier)
    switch_to(owner_client, cashier)
    assert owner_client.get(PROMOTIONS).status_code == 403
    response = owner_client.post(f'{PROMOTIONS}{promotion["id"]}/end')
    assert response.status_code == 403


def test_a_promotion_must_make_sense(
    owner_client: TestClient, uniforms: dict
) -> None:
    body = {
        'name': 'Aneh',
        'discount_kind': 'percentage',
        'value': 120,
        'target_kind': 'skus',
        'target_ids': [uniforms['shirt'].id],
        'starts_at': NOW.isoformat(),
        'ends_at': (NOW + timedelta(days=1)).isoformat(),
    }
    assert owner_client.post(PROMOTIONS, json=body).status_code == 422
    backwards = {
        **body,
        'value': 10,
        'ends_at': (NOW - timedelta(days=1)).isoformat(),
    }
    assert owner_client.post(PROMOTIONS, json=backwards).status_code == 422
    unknown = {**body, 'value': 10, 'target_ids': [999999]}
    assert owner_client.post(PROMOTIONS, json=unknown).status_code == 404
