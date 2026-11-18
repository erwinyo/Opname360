from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_user, new_category, new_product, sign_in

from opname360.models import Role


CATEGORIES = '/api/v1/categories/'


def test_category_holds_sub_categories_with_product_counts(
    owner_client: TestClient,
) -> None:
    seragam = new_category(
        owner_client, 'Seragam', ('Topi', 'Dasi'), costing_method='fifo'
    )
    new_category(owner_client, 'ATK', ())
    dasi = seragam['sub_categories'][0]
    new_product(owner_client, dasi['id'], 'Dasi SD')

    categories = owner_client.get(CATEGORIES).json()

    assert [category['name'] for category in categories] == ['ATK', 'Seragam']
    assert categories[1]['costing_method'] == 'fifo'
    assert [
        (sub['name'], sub['product_count'])
        for sub in categories[1]['sub_categories']
    ] == [('Dasi', 1), ('Topi', 0)]


def test_new_category_uses_moving_average_unless_told_otherwise(
    owner_client: TestClient,
) -> None:
    created = owner_client.post(CATEGORIES, json={'name': 'ATK'})

    assert created.status_code == 201
    assert created.json()['costing_method'] == 'moving_average'


def test_category_name_is_unique_whatever_the_case(
    owner_client: TestClient,
) -> None:
    new_category(owner_client, 'Seragam', ())

    again = owner_client.post(CATEGORIES, json={'name': ' seragam '})

    assert again.status_code == 409
    assert 'sudah ada' in again.json()['detail']


def test_sub_category_name_is_unique_within_its_category_only(
    owner_client: TestClient,
) -> None:
    seragam = new_category(owner_client, 'Seragam', ('Topi',))
    non_seragam = new_category(owner_client, 'Non-Seragam', ())

    same_category = owner_client.post(
        f'{CATEGORIES}{seragam["id"]}/sub-categories', json={'name': 'topi'}
    )
    other_category = owner_client.post(
        f'{CATEGORIES}{non_seragam["id"]}/sub-categories',
        json={'name': 'Topi'},
    )

    assert same_category.status_code == 409
    assert other_category.status_code == 201


def test_blank_name_is_refused(owner_client: TestClient) -> None:
    blank = owner_client.post(CATEGORIES, json={'name': '   '})

    assert blank.status_code == 400
    assert blank.json()['detail'] == 'Nama kategori wajib diisi.'


def test_rename_category_and_sub_category(owner_client: TestClient) -> None:
    category = new_category(owner_client, 'Seragm', ('Tpi',))
    sub_category = category['sub_categories'][0]

    owner_client.patch(
        f'{CATEGORIES}{category["id"]}',
        json={'name': 'Seragam'},
    )
    renamed = owner_client.patch(
        f'{CATEGORIES}sub-categories/{sub_category["id"]}',
        json={'name': 'Topi'},
    ).json()

    assert renamed['name'] == 'Seragam'
    assert renamed['sub_categories'][0]['name'] == 'Topi'


def test_category_with_products_cannot_be_deleted(
    owner_client: TestClient,
) -> None:
    category = new_category(owner_client, 'Seragam', ('Topi', 'Dasi'))
    dasi, topi = category['sub_categories']
    product = new_product(owner_client, topi['id'], 'Topi SD')
    category_url = f'{CATEGORIES}{category["id"]}'
    topi_url = f'{CATEGORIES}sub-categories/{topi["id"]}'

    assert owner_client.delete(category_url).status_code == 409
    assert owner_client.delete(topi_url).status_code == 409
    # An empty Sub-category can go at any time.
    assert (
        owner_client.delete(
            f'{CATEGORIES}sub-categories/{dasi["id"]}'
        ).status_code
        == 204
    )

    owner_client.delete(f'/api/v1/products/{product["id"]}')

    # Deleting the Category takes its remaining Sub-categories with it.
    assert owner_client.delete(category_url).status_code == 204
    assert owner_client.get(CATEGORIES).json() == []


def test_admin_manages_the_catalogue_but_a_cashier_cannot(
    client: TestClient, session: Session
) -> None:
    make_user(session, 'admin', Role.admin)
    make_user(session, 'kasir', Role.cashier)

    sign_in(client, 'admin')
    assert client.post(CATEGORIES, json={'name': 'ATK'}).status_code == 201
    assert client.get('/api/v1/products/').status_code == 200

    sign_in(client, 'kasir')
    assert client.get(CATEGORIES).status_code == 403
    assert client.post(CATEGORIES, json={'name': 'Obat'}).status_code == 403
    assert client.get('/api/v1/products/').status_code == 403
