import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import new_category, new_product, sku_row

from opname360.models import ActivityLog


PRODUCTS = '/api/v1/products/'


@pytest.fixture
def kemeja(owner_client: TestClient) -> int:
    """The id of Sub-category Kemeja, in Category Seragam."""
    return new_category(owner_client)['sub_categories'][0]['id']


def save(client: TestClient, product: dict, **changes: object):
    body = {
        'name': product['name'],
        'sub_category_id': product['sub_category_id'],
        'skus': product['skus'],
        **changes,
    }
    return client.put(f'{PRODUCTS}{product["id"]}', json=body)


def test_product_is_created_with_its_skus(
    owner_client: TestClient, kemeja: int
) -> None:
    product = new_product(
        owner_client,
        kemeja,
        skus=[
            sku_row(size='10', color='Putih'),
            sku_row(size='12', color='Putih', selling_price=90000),
        ],
    )

    assert product['category_name'] == 'Seragam'
    assert product['sub_category_name'] == 'Kemeja'
    assert [
        (sku['size'], sku['selling_price']) for sku in product['skus']
    ] == [
        ('10', 85000),
        ('12', 90000),
    ]
    assert owner_client.get(f'{PRODUCTS}{product["id"]}').json() == product


def test_sku_without_a_barcode_gets_a_generated_one(
    owner_client: TestClient, kemeja: int
) -> None:
    product = new_product(
        owner_client, kemeja, skus=[sku_row(size='10'), sku_row(size='12')]
    )
    first, second = product['skus']

    for sku in (first, second):
        assert sku['barcode'] == f'2{sku["id"]:07d}'
        assert sku['code'] == f'S{sku["id"]:06d}'
    assert first['barcode'] != second['barcode']


def test_manufacturer_barcode_and_shop_code_are_kept(
    owner_client: TestClient, kemeja: int
) -> None:
    product = new_product(
        owner_client,
        kemeja,
        'Pulpen Biru',
        skus=[sku_row(size=None, barcode=' 8991234567890 ', code='PLP-B')],
    )

    assert product['skus'][0]['barcode'] == '8991234567890'
    assert product['skus'][0]['code'] == 'PLP-B'


def test_a_barcode_belongs_to_exactly_one_sku(
    owner_client: TestClient, kemeja: int
) -> None:
    new_product(
        owner_client,
        kemeja,
        'Pulpen Biru',
        skus=[sku_row(size=None, color='Biru', barcode='8991234567890')],
    )
    body = {'name': 'Pulpen Merah', 'sub_category_id': kemeja}

    other_product = owner_client.post(
        PRODUCTS, json={**body, 'skus': [sku_row(barcode='8991234567890')]}
    )
    same_product = owner_client.post(
        PRODUCTS,
        json={
            **body,
            'skus': [
                sku_row(size='A', barcode='111'),
                sku_row(size='B', barcode='111'),
            ],
        },
    )

    assert other_product.status_code == 409
    assert other_product.json()['detail'] == (
        'Barcode 8991234567890 sudah dipakai oleh Pulpen Biru (Biru).'
    )
    assert same_product.status_code == 409
    assert owner_client.get(PRODUCTS).json()['total'] == 1


def test_a_code_belongs_to_exactly_one_sku_whatever_the_case(
    owner_client: TestClient, kemeja: int
) -> None:
    new_product(owner_client, kemeja, 'Pulpen Biru', [sku_row(code='PLP-1')])

    clash = owner_client.post(
        PRODUCTS,
        json={
            'name': 'Pulpen Merah',
            'sub_category_id': kemeja,
            'skus': [sku_row(code='plp-1')],
        },
    )

    assert clash.status_code == 409
    assert 'Kode PLP-1 sudah dipakai' in clash.json()['detail']


def test_a_variant_appears_once_per_product(
    owner_client: TestClient, kemeja: int
) -> None:
    body = {'name': 'Kemeja Putih SD', 'sub_category_id': kemeja}

    repeated = owner_client.post(
        PRODUCTS,
        json={**body, 'skus': [sku_row(size='10'), sku_row(size=' 10 ')]},
    )
    two_plain = owner_client.post(
        PRODUCTS,
        json={**body, 'skus': [sku_row(size=None), sku_row(size='')]},
    )

    assert repeated.status_code == 409
    assert repeated.json()['detail'] == 'Varian 10 muncul dua kali.'
    assert two_plain.status_code == 409


def test_product_name_is_unique_within_its_sub_category_only(
    owner_client: TestClient,
) -> None:
    kemeja, celana = new_category(
        owner_client, 'Seragam', ('Kemeja', 'Celana')
    )['sub_categories']
    kemeja, celana = sorted((kemeja, celana), key=lambda sub: sub['name'])[
        ::-1
    ]
    new_product(owner_client, kemeja['id'], 'Seragam SD')
    body = {'name': 'seragam sd', 'skus': [sku_row()]}

    same = owner_client.post(
        PRODUCTS, json={**body, 'sub_category_id': kemeja['id']}
    )
    other = owner_client.post(
        PRODUCTS, json={**body, 'sub_category_id': celana['id']}
    )

    assert same.status_code == 409
    assert other.status_code == 201


@pytest.mark.parametrize(
    'row',
    [
        sku_row(purchase_pack_name='box'),
        sku_row(purchase_pack_size=12),
        sku_row(purchase_pack_name='box', purchase_pack_size=0),
        sku_row(selling_price=-1),
        sku_row(stock_unit=''),
    ],
)
def test_invalid_sku_rows_are_refused(
    owner_client: TestClient, kemeja: int, row: dict
) -> None:
    response = owner_client.post(
        PRODUCTS, json={'name': 'X', 'sub_category_id': kemeja, 'skus': [row]}
    )

    assert response.status_code == 422


def test_purchase_pack_is_stored_with_name_and_size(
    owner_client: TestClient, kemeja: int
) -> None:
    product = new_product(
        owner_client,
        kemeja,
        'Pulpen Biru',
        skus=[sku_row(purchase_pack_name='box', purchase_pack_size=12)],
    )

    assert product['skus'][0]['purchase_pack_name'] == 'box'
    assert float(product['skus'][0]['purchase_pack_size']) == 12


def test_product_needs_at_least_one_sku_and_a_real_sub_category(
    owner_client: TestClient, kemeja: int
) -> None:
    no_skus = owner_client.post(
        PRODUCTS, json={'name': 'X', 'sub_category_id': kemeja, 'skus': []}
    )
    no_sub_category = owner_client.post(
        PRODUCTS,
        json={'name': 'X', 'sub_category_id': 9999, 'skus': [sku_row()]},
    )

    assert no_skus.status_code == 422
    assert no_sub_category.status_code == 404


def test_saving_a_product_makes_its_skus_match_the_form(
    owner_client: TestClient, kemeja: int
) -> None:
    product = new_product(
        owner_client,
        kemeja,
        skus=[sku_row(size='10'), sku_row(size='12', barcode='111')],
    )
    size_10, size_12 = product['skus']

    saved = save(
        owner_client,
        product,
        name='Kemeja Putih SD Lengan Pendek',
        skus=[
            {**size_10, 'selling_price': 88000, 'is_active': False},
            # Size 12 is dropped; the new size 14 takes over its Barcode.
            sku_row(size='14', barcode='111'),
        ],
    )

    assert saved.status_code == 200, saved.text
    assert saved.json()['name'] == 'Kemeja Putih SD Lengan Pendek'
    skus = {sku['size']: sku for sku in saved.json()['skus']}
    assert set(skus) == {'10', '14'}
    assert skus['10']['id'] == size_10['id']
    assert skus['10']['selling_price'] == 88000
    assert skus['10']['is_active'] is False
    assert skus['14']['barcode'] == '111'
    assert skus['14']['id'] != size_12['id']


def test_a_sku_of_another_product_cannot_be_changed_through_this_one(
    owner_client: TestClient, kemeja: int
) -> None:
    kemeja_sd = new_product(owner_client, kemeja, 'Kemeja SD')
    kemeja_smp = new_product(owner_client, kemeja, 'Kemeja SMP')

    response = save(owner_client, kemeja_sd, skus=kemeja_smp['skus'])

    assert response.status_code == 404


def test_price_changes_are_kept_with_who_made_them(
    owner_client: TestClient, session: Session, kemeja: int
) -> None:
    product = new_product(owner_client, kemeja, skus=[sku_row(size='10')])
    sku = product['skus'][0]
    history_url = f'{PRODUCTS}skus/{sku["id"]}/price-changes'

    save(owner_client, product, skus=[{**sku, 'selling_price': 90000}])
    # Saving again without touching the price adds nothing.
    save(owner_client, product, skus=[{**sku, 'selling_price': 90000}])

    history = owner_client.get(history_url).json()
    assert [
        (change['old_price'], change['new_price'], change['changed_by_name'])
        for change in history
    ] == [(85000, 90000, 'Owner'), (None, 85000, 'Owner')]
    logged = session.exec(
        select(ActivityLog).where(ActivityLog.action == 'sku.price_change')
    ).one()
    assert logged.summary == (
        'Harga jual Kemeja Putih SD (10) berubah '
        'dari Rp 85.000 menjadi Rp 90.000.'
    )


def test_search_matches_name_code_and_barcode(
    owner_client: TestClient, kemeja: int
) -> None:
    new_product(owner_client, kemeja, 'Kemeja Putih SD')
    new_product(
        owner_client,
        kemeja,
        'Pulpen Biru',
        skus=[sku_row(code='PLP-77', barcode='8991234567890')],
    )

    def found(search: str) -> list[str]:
        page = owner_client.get(PRODUCTS, params={'search': search}).json()
        return [product['name'] for product in page['items']]

    assert found('putih') == ['Kemeja Putih SD']
    assert found('plp-77') == ['Pulpen Biru']
    assert found('8991234') == ['Pulpen Biru']
    assert found('100%') == []
    assert found('') == ['Kemeja Putih SD', 'Pulpen Biru']


def test_products_filter_by_category_and_come_in_pages(
    owner_client: TestClient, kemeja: int
) -> None:
    atk = new_category(owner_client, 'ATK', ('Pulpen',))
    pulpen = atk['sub_categories'][0]['id']
    for name in ('Pulpen A', 'Pulpen B', 'Pulpen C'):
        new_product(owner_client, pulpen, name)
    new_product(owner_client, kemeja, 'Kemeja Putih SD')

    by_category = owner_client.get(
        PRODUCTS, params={'category_id': atk['id'], 'limit': 2, 'offset': 2}
    ).json()
    by_sub_category = owner_client.get(
        PRODUCTS, params={'sub_category_id': kemeja}
    ).json()

    assert by_category['total'] == 3
    assert [product['name'] for product in by_category['items']] == [
        'Pulpen C'
    ]
    assert by_sub_category['total'] == 1


def test_deleting_a_product_removes_its_skus(
    owner_client: TestClient, kemeja: int
) -> None:
    product = new_product(owner_client, kemeja, skus=[sku_row(barcode='111')])

    deleted = owner_client.delete(f'{PRODUCTS}{product["id"]}')

    assert deleted.status_code == 204
    assert owner_client.get(f'{PRODUCTS}{product["id"]}').status_code == 404
    # The Barcode is free again.
    new_product(owner_client, kemeja, 'Lain', skus=[sku_row(barcode='111')])
