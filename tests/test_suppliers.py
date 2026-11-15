from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_user, new_supplier, sign_in

from opname360.models import Role


SUPPLIERS = '/api/v1/suppliers/'


def test_suppliers_are_listed_by_name(owner_client: TestClient) -> None:
    new_supplier(owner_client, 'PT Tekstil')
    owner_client.post(
        SUPPLIERS,
        json={'name': 'CV Alat Tulis', 'phone': ' 0812 ', 'address': ''},
    )

    suppliers = owner_client.get(SUPPLIERS).json()

    assert [supplier['name'] for supplier in suppliers] == [
        'CV Alat Tulis',
        'PT Tekstil',
    ]
    assert suppliers[0]['phone'] == '0812'
    assert suppliers[0]['address'] is None


def test_supplier_name_is_unique_whatever_the_case(
    owner_client: TestClient,
) -> None:
    new_supplier(owner_client, 'PT Tekstil')

    again = owner_client.post(SUPPLIERS, json={'name': 'pt tekstil'})

    assert again.status_code == 409


def test_supplier_can_be_renamed_and_deactivated(
    owner_client: TestClient,
) -> None:
    supplier = new_supplier(owner_client, 'PT Tekstl')
    url = f'{SUPPLIERS}{supplier["id"]}'

    renamed = owner_client.patch(url, json={'name': 'PT Tekstil'})
    deactivated = owner_client.patch(url, json={'is_active': False})

    assert renamed.json()['name'] == 'PT Tekstil'
    assert deactivated.json()['is_active'] is False
    assert deactivated.json()['name'] == 'PT Tekstil'


def test_a_cashier_cannot_see_suppliers(
    client: TestClient, session: Session
) -> None:
    make_user(session, 'kasir', Role.cashier)
    sign_in(client, 'kasir')

    assert client.get(SUPPLIERS).status_code == 403
