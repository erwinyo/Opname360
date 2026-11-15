from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import (
    make_user,
    new_category,
    new_product,
    new_receipt,
    new_sku,
    new_supplier,
    sign_in,
    sku_row,
)

from opname360.models import MovementReason, Role, Sku
from opname360.services import costing


STOCK = '/api/v1/stock/'


def line(sku_id: int | None, quantity: float, unit_cost: float) -> dict:
    return {'sku_id': sku_id, 'quantity': quantity, 'unit_cost': unit_cost}


def oversell(session: Session, sku: Sku, quantity: int) -> None:
    costing.issue(
        session,
        sku=sku,
        location_id=1,
        quantity=Decimal(quantity),
        reason=MovementReason.supplier_return,
        source=costing.Source('test', 1, 'TEST-1'),
        actor=None,
    )
    session.commit()


def test_stock_lists_every_sku_with_quantity_and_value(
    owner_client: TestClient,
) -> None:
    sub_category = new_category(owner_client)['sub_categories'][0]['id']
    product = new_product(
        owner_client,
        sub_category,
        'Kemeja Putih SD',
        [sku_row(size='10'), sku_row(size='12')],
    )
    size_10, size_12 = product['skus']
    supplier = new_supplier(owner_client)
    new_receipt(
        owner_client,
        supplier['id'],
        [line(size_10['id'], 10, 5000), line(size_10['id'], 5, 6500)],
    )

    page = owner_client.get(STOCK).json()

    assert page['total'] == 2
    assert Decimal(page['total_value']) == 82500
    first, second = page['items']
    assert (first['product_name'], first['size']) == ('Kemeja Putih SD', '10')
    assert first['category_name'] == 'Seragam'
    assert first['sub_category_name'] == 'Kemeja'
    assert Decimal(first['quantity']) == 15
    assert Decimal(first['value']) == 82500
    # A SKU that never moved is listed with nothing on hand.
    assert second['sku_id'] == size_12['id']
    assert Decimal(second['quantity']) == 0
    assert Decimal(second['value']) == 0


def test_stock_filters_by_search_category_and_negative_stock(
    owner_client: TestClient, session: Session
) -> None:
    kemeja = new_sku(owner_client, session, barcode='111')
    pulpen = new_sku(owner_client, session, barcode='222')
    supplier = new_supplier(owner_client)
    new_receipt(owner_client, supplier['id'], [line(kemeja.id, 10, 5000)])
    oversell(session, pulpen, 3)

    def skus(**params: str | int | bool) -> list[int]:
        page = owner_client.get(STOCK, params=params).json()
        return [item['sku_id'] for item in page['items']]

    category_of_kemeja = kemeja.product.sub_category.category_id

    assert skus(search='222') == [pulpen.id]
    assert skus(category_id=category_of_kemeja) == [kemeja.id]
    assert skus(negative_only=True) == [pulpen.id]
    assert set(skus()) == {kemeja.id, pulpen.id}


def test_stock_card_shows_movements_newest_first_with_running_balance(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    first = new_receipt(owner_client, supplier['id'], [line(sku.id, 10, 5000)])
    second = new_receipt(owner_client, supplier['id'], [line(sku.id, 5, 6500)])

    card = owner_client.get(f'{STOCK}skus/{sku.id}/card').json()

    assert card['location']['name'] == 'Toko'
    assert Decimal(card['sku']['quantity']) == 15
    assert Decimal(card['sku']['value']) == 82500
    assert card['total'] == 2
    newest, oldest = card['items']
    assert newest['document_number'] == second['number']
    assert newest['document_type'] == 'goods_receipt'
    assert newest['document_id'] == second['id']
    assert newest['reason'] == 'goods_receipt'
    assert newest['created_by_name'] == 'Owner'
    assert Decimal(newest['quantity']) == 5
    assert Decimal(newest['unit_cost']) == 6500
    assert Decimal(newest['quantity_after']) == 15
    assert Decimal(newest['value_after']) == 82500
    assert oldest['document_number'] == first['number']
    assert Decimal(oldest['quantity_after']) == 10


def test_stock_card_comes_in_pages(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    for _ in range(3):
        new_receipt(owner_client, supplier['id'], [line(sku.id, 1, 100)])

    card = owner_client.get(
        f'{STOCK}skus/{sku.id}/card', params={'limit': 2, 'offset': 2}
    ).json()

    assert card['total'] == 3
    assert len(card['items']) == 1
    assert Decimal(card['items'][0]['quantity_after']) == 1


def test_stock_card_of_an_unknown_sku_is_not_found(
    owner_client: TestClient,
) -> None:
    assert owner_client.get(f'{STOCK}skus/9999/card').status_code == 404


def test_the_shop_starts_with_one_location(owner_client: TestClient) -> None:
    locations = owner_client.get(f'{STOCK}locations').json()

    assert [location['name'] for location in locations] == ['Toko']


def test_a_cashier_cannot_see_stock(
    client: TestClient, session: Session
) -> None:
    make_user(session, 'kasir', Role.cashier)
    sign_in(client, 'kasir')

    assert client.get(STOCK).status_code == 403
    assert client.get(f'{STOCK}skus/1/card').status_code == 403


def test_a_sku_with_stock_history_cannot_be_deleted(
    owner_client: TestClient, session: Session
) -> None:
    sub_category = new_category(owner_client)['sub_categories'][0]['id']
    product = new_product(
        owner_client,
        sub_category,
        'Kemeja Putih SD',
        [sku_row(size='10'), sku_row(size='12')],
    )
    size_10, size_12 = product['skus']
    supplier = new_supplier(owner_client)
    new_receipt(owner_client, supplier['id'], [line(size_10['id'], 10, 5000)])
    url = f'/api/v1/products/{product["id"]}'
    body = {'name': product['name'], 'sub_category_id': sub_category}

    drop_moved = owner_client.put(url, json={**body, 'skus': [size_12]})
    drop_unmoved = owner_client.put(url, json={**body, 'skus': [size_10]})
    delete_product = owner_client.delete(url)

    assert drop_moved.status_code == 409
    assert (
        'Kemeja Putih SD (10) sudah punya riwayat stok'
        in (drop_moved.json()['detail'])
    )
    assert drop_unmoved.status_code == 200
    assert delete_product.status_code == 409


def test_costing_method_is_fixed_once_stock_has_moved(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'moving_average')
    category_id = sku.product.sub_category.category_id
    url = f'/api/v1/categories/{category_id}'
    assert (
        owner_client.patch(url, json={'costing_method': 'fifo'}).status_code
        == 200
    )
    supplier = new_supplier(owner_client)
    new_receipt(owner_client, supplier['id'], [line(sku.id, 10, 5000)])

    change = owner_client.patch(url, json={'costing_method': 'moving_average'})
    rename = owner_client.patch(url, json={'name': 'Nama Baru'})

    assert change.status_code == 409
    assert 'stoknya sudah bergerak' in change.json()['detail']
    assert rename.status_code == 200


def test_scanning_finds_a_sku_by_barcode_code_or_name(
    owner_client: TestClient,
) -> None:
    sub_category = new_category(owner_client)['sub_categories'][0]['id']
    new_product(
        owner_client,
        sub_category,
        'Kemeja Putih SD',
        [
            sku_row(size='10', barcode='8990001', code='KMJ-10'),
            sku_row(size='12', barcode='8990002', is_active=False),
        ],
    )
    new_product(owner_client, sub_category, 'Kemeja Batik', [sku_row()])

    def found(query: str) -> list[tuple[str, str | None]]:
        options = owner_client.get(
            '/api/v1/products/skus/search', params={'query': query}
        ).json()
        return [(option['product_name'], option['size']) for option in options]

    assert found('8990001') == [('Kemeja Putih SD', '10')]
    assert found('kmj-10') == [('Kemeja Putih SD', '10')]
    assert found('kemeja') == [
        ('Kemeja Batik', '10'),
        ('Kemeja Putih SD', '10'),
    ]
    # An inactive SKU is not offered.
    assert found('8990002') == []
    assert found('  ') == []
