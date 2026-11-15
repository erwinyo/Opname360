import math

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, delete, select

from opname360.core.errors import LockedError, UnauthorizedError
from opname360.core.security import hash_token, new_token, verify_password
from opname360.models import User, UserSession
from opname360.services import activity_log


MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)
SESSION_IDLE = timedelta(hours=12)
# How stale `last_used_at` may get before a request rewrites it.
TOUCH_INTERVAL = timedelta(minutes=1)

WRONG_CREDENTIALS = 'Nama pengguna atau kata sandi salah.'


def authenticate(session: Session, username: str, password: str) -> User:
    user = session.exec(
        select(User).where(User.username == username.strip().lower())
    ).first()
    now = datetime.now(UTC)

    if user is None or not user.is_active:
        verify_password(password, None)
        raise UnauthorizedError(WRONG_CREDENTIALS)

    if user.locked_until and user.locked_until > now:
        minutes = math.ceil((user.locked_until - now).total_seconds() / 60)
        raise LockedError(
            'Akun dikunci karena terlalu banyak percobaan masuk. '
            f'Coba lagi dalam {minutes} menit.'
        )

    if not verify_password(password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.failed_logins = 0
            user.locked_until = now + LOCKOUT
            activity_log.record(
                session,
                actor=user,
                action='auth.locked',
                summary=(
                    f'Akun {user.username} dikunci setelah '
                    f'{MAX_FAILED_LOGINS} kali gagal masuk.'
                ),
                entity_type='user',
                entity_id=user.id,
            )
        session.add(user)
        session.commit()
        raise UnauthorizedError(WRONG_CREDENTIALS)

    if user.failed_logins or user.locked_until:
        user.failed_logins = 0
        user.locked_until = None
        session.add(user)
        session.commit()
    return user


def start_session(session: Session, user: User) -> str:
    """Return the token to hand to the browser; only its hash is kept."""
    assert user.id is not None
    token = new_token()
    session.add(UserSession(token_hash=hash_token(token), user_id=user.id))
    session.commit()
    return token


def get_session_user(session: Session, token: str) -> User | None:
    user_session = session.get(UserSession, hash_token(token))
    if user_session is None:
        return None

    now = datetime.now(UTC)
    idle = now - user_session.last_used_at
    if idle > SESSION_IDLE:
        session.delete(user_session)
        session.commit()
        return None

    user = session.get(User, user_session.user_id)
    if user is None or not user.is_active:
        return None

    if idle > TOUCH_INTERVAL:
        user_session.last_used_at = now
        session.add(user_session)
        session.commit()
    return user


def end_session(session: Session, token: str) -> None:
    session.exec(
        delete(UserSession).where(
            col(UserSession.token_hash) == hash_token(token)
        )
    )
    session.commit()


def end_user_sessions(session: Session, user: User) -> None:
    """Sign the user out everywhere. The caller commits."""
    session.exec(
        delete(UserSession).where(col(UserSession.user_id) == user.id)
    )
