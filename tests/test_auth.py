from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import PASSWORD, make_user, sign_in

from opname360.models import ActivityLog, Role, User, UserSession


ME = '/api/v1/auth/me'


def test_sign_in_returns_the_user_without_the_password_hash(
    client: TestClient, owner: User
) -> None:
    response = sign_in(client, 'owner')

    assert response.status_code == 200
    assert response.json()['username'] == 'owner'
    assert response.json()['role'] == 'owner'
    assert 'password_hash' not in response.json()
    assert client.get(ME).json()['username'] == 'owner'


def test_session_cookie_is_not_readable_by_scripts(
    client: TestClient, owner: User
) -> None:
    cookie = sign_in(client, 'owner').headers['set-cookie'].lower()

    assert 'httponly' in cookie
    assert 'samesite=lax' in cookie


def test_username_is_not_case_sensitive(
    client: TestClient, owner: User
) -> None:
    assert sign_in(client, '  OWNER ').status_code == 200


def test_wrong_password_and_unknown_user_get_the_same_answer(
    client: TestClient, owner: User
) -> None:
    wrong_password = sign_in(client, 'owner', 'salah-salah')
    unknown_user = sign_in(client, 'nobody', PASSWORD)

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_inactive_user_cannot_sign_in(
    client: TestClient, session: Session
) -> None:
    make_user(session, 'former', Role.cashier, is_active=False)

    assert sign_in(client, 'former').status_code == 401


def test_five_failed_sign_ins_lock_the_account(
    client: TestClient, session: Session, owner: User
) -> None:
    for _ in range(5):
        assert sign_in(client, 'owner', 'salah-salah').status_code == 401

    locked = sign_in(client, 'owner', PASSWORD)

    assert locked.status_code == 423
    assert '15 menit' in locked.json()['detail']
    logged = session.exec(
        select(ActivityLog).where(ActivityLog.action == 'auth.locked')
    ).one()
    assert logged.entity_id == owner.id


def test_lock_ends_after_fifteen_minutes(
    client: TestClient, session: Session, owner: User
) -> None:
    for _ in range(5):
        sign_in(client, 'owner', 'salah-salah')
    session.refresh(owner)
    assert owner.locked_until is not None
    lock_length = owner.locked_until - datetime.now(UTC)
    assert timedelta(minutes=14) < lock_length <= timedelta(minutes=15)

    owner.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    session.add(owner)
    session.commit()

    assert sign_in(client, 'owner', PASSWORD).status_code == 200


def test_a_successful_sign_in_resets_the_failure_count(
    client: TestClient, owner: User
) -> None:
    for _ in range(4):
        sign_in(client, 'owner', 'salah-salah')
    assert sign_in(client, 'owner', PASSWORD).status_code == 200
    for _ in range(4):
        sign_in(client, 'owner', 'salah-salah')

    assert sign_in(client, 'owner', PASSWORD).status_code == 200


def test_me_requires_a_session(client: TestClient) -> None:
    assert client.get(ME).status_code == 401


def test_sign_out_ends_the_session(
    owner_client: TestClient, session: Session
) -> None:
    token = owner_client.cookies['opname360_session']

    assert owner_client.post('/api/v1/auth/logout').status_code == 204

    assert session.exec(select(UserSession)).all() == []
    owner_client.cookies.set('opname360_session', token)
    assert owner_client.get(ME).status_code == 401


def test_session_ends_after_twelve_idle_hours(
    owner_client: TestClient, session: Session
) -> None:
    user_session = session.exec(select(UserSession)).one()
    user_session.last_used_at = datetime.now(UTC) - timedelta(hours=11)
    session.add(user_session)
    session.commit()
    assert owner_client.get(ME).status_code == 200

    user_session = session.exec(select(UserSession)).one()
    user_session.last_used_at = datetime.now(UTC) - timedelta(hours=12.1)
    session.add(user_session)
    session.commit()

    assert owner_client.get(ME).status_code == 401


def test_only_the_token_hash_is_stored(
    owner_client: TestClient, session: Session
) -> None:
    token = owner_client.cookies['opname360_session']

    assert session.exec(select(UserSession)).one().token_hash != token


def test_a_change_from_another_site_is_refused(
    owner_client: TestClient,
) -> None:
    foreign = owner_client.post(
        '/api/v1/auth/logout', headers={'Origin': 'https://evil.example'}
    )
    own = owner_client.post(
        '/api/v1/auth/logout', headers={'Origin': 'http://testserver'}
    )

    assert foreign.status_code == 403
    assert own.status_code == 204
