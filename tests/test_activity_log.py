from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import make_user, new_category, sign_in

from opname360.models import Role


LOG = '/api/v1/activity-log/'


def test_owner_reads_the_log_newest_first_with_who_did_what(
    owner_client: TestClient,
) -> None:
    new_category(owner_client, 'Seragam', ('Topi',))

    page = owner_client.get(LOG).json()

    assert page['total'] == 2
    newest, oldest = page['items']
    assert newest['action'] == 'sub_category.create'
    assert newest['summary'] == 'Menambah sub-kategori Topi di Seragam.'
    assert newest['user_name'] == 'Owner'
    assert oldest['action'] == 'category.create'


def test_log_filters_by_user(
    client: TestClient, session: Session, owner_client: TestClient
) -> None:
    admin = make_user(session, 'admin', Role.admin)
    new_category(owner_client, 'Seragam', ())
    sign_in(client, 'admin')
    new_category(client, 'ATK', ())
    sign_in(client, 'owner')

    page = client.get(LOG, params={'user_id': admin.id}).json()

    assert [entry['summary'] for entry in page['items']] == [
        'Menambah kategori ATK (HPP Rata-rata).'
    ]


def test_only_the_owner_reads_the_log(
    client: TestClient, session: Session
) -> None:
    make_user(session, 'admin', Role.admin)
    sign_in(client, 'admin')

    assert client.get(LOG).status_code == 403
