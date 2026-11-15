import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import PASSWORD, make_user, sign_in

from opname360.main import app
from opname360.models import ActivityLog, Role, User


USERS = '/api/v1/users/'
NEW_CASHIER = {
    'username': 'Sari',
    'full_name': 'Sari Dewi',
    'role': 'cashier',
    'password': 'kata-sandi-1',
}


def test_owner_creates_a_user_who_can_then_sign_in(
    owner_client: TestClient,
) -> None:
    created = owner_client.post(USERS, json=NEW_CASHIER)

    assert created.status_code == 201
    assert created.json()['username'] == 'sari'
    assert 'password' not in created.text
    usernames = [user['username'] for user in owner_client.get(USERS).json()]
    assert usernames == ['owner', 'sari']
    assert sign_in(TestClient(app), 'sari', 'kata-sandi-1').status_code == 200


@pytest.mark.parametrize('role', [Role.admin, Role.cashier])
def test_only_the_owner_manages_users(
    client: TestClient, session: Session, role: Role
) -> None:
    target = make_user(session, 'target', Role.cashier)
    make_user(session, 'staff', role)
    sign_in(client, 'staff')

    assert client.get(USERS).status_code == 403
    assert client.post(USERS, json=NEW_CASHIER).status_code == 403
    assert (
        client.patch(f'{USERS}{target.id}', json={'role': 'owner'}).status_code
        == 403
    )
    assert (
        client.post(
            f'{USERS}{target.id}/password', json={'password': 'x' * 8}
        ).status_code
        == 403
    )


def test_signed_out_visitor_cannot_list_users(client: TestClient) -> None:
    assert client.get(USERS).status_code == 401


def test_username_must_be_unique(owner_client: TestClient) -> None:
    owner_client.post(USERS, json=NEW_CASHIER)

    again = owner_client.post(USERS, json={**NEW_CASHIER, 'username': 'SARI'})

    assert again.status_code == 409


def test_password_needs_eight_characters(owner_client: TestClient) -> None:
    short = owner_client.post(
        USERS, json={**NEW_CASHIER, 'password': '1234567'}
    )

    assert short.status_code == 422


def test_deactivated_user_is_signed_out_at_once(
    owner_client: TestClient, session: Session
) -> None:
    cashier = make_user(session, 'sari', Role.cashier)
    cashier_client = TestClient(app)
    sign_in(cashier_client, 'sari')
    assert cashier_client.get('/api/v1/auth/me').status_code == 200

    owner_client.patch(f'{USERS}{cashier.id}', json={'is_active': False})

    assert cashier_client.get('/api/v1/auth/me').status_code == 401
    assert sign_in(cashier_client, 'sari').status_code == 401


def test_the_last_active_owner_cannot_be_removed(
    owner_client: TestClient, owner: User
) -> None:
    deactivate = owner_client.patch(
        f'{USERS}{owner.id}', json={'is_active': False}
    )
    demote = owner_client.patch(f'{USERS}{owner.id}', json={'role': 'admin'})

    assert deactivate.status_code == demote.status_code == 409
    assert owner_client.get('/api/v1/auth/me').json()['role'] == 'owner'


def test_an_owner_can_be_removed_while_another_remains(
    owner_client: TestClient, session: Session
) -> None:
    second = make_user(session, 'second', Role.owner)

    demote = owner_client.patch(f'{USERS}{second.id}', json={'role': 'admin'})

    assert demote.status_code == 200
    assert demote.json()['role'] == 'admin'


def test_password_reset_signs_the_user_out_and_unlocks_the_account(
    owner_client: TestClient, session: Session
) -> None:
    cashier = make_user(session, 'sari', Role.cashier)
    cashier_client = TestClient(app)
    sign_in(cashier_client, 'sari')
    for _ in range(5):
        sign_in(TestClient(app), 'sari', 'salah-salah')

    reset = owner_client.post(
        f'{USERS}{cashier.id}/password', json={'password': 'sandi-baru-9'}
    )

    assert reset.status_code == 204
    assert cashier_client.get('/api/v1/auth/me').status_code == 401
    assert sign_in(cashier_client, 'sari', PASSWORD).status_code == 401
    assert sign_in(cashier_client, 'sari', 'sandi-baru-9').status_code == 200


def test_unknown_user_is_not_found(owner_client: TestClient) -> None:
    assert (
        owner_client.patch(f'{USERS}9999', json={'role': 'admin'}).status_code
        == 404
    )


def test_user_changes_are_in_the_activity_log(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    user_id = owner_client.post(USERS, json=NEW_CASHIER).json()['id']
    owner_client.patch(f'{USERS}{user_id}', json={'role': 'admin'})
    owner_client.post(
        f'{USERS}{user_id}/password', json={'password': 'sandi-baru-9'}
    )

    entries = session.exec(
        select(ActivityLog)
        .where(ActivityLog.entity_id == user_id)
        .order_by(col(ActivityLog.id))
    ).all()

    assert [entry.action for entry in entries] == [
        'user.create',
        'user.update',
        'user.reset_password',
    ]
    assert all(entry.user_id == owner.id for entry in entries)
    assert 'peran menjadi Admin' in entries[1].summary
