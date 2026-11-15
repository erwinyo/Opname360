from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError, NotFoundError
from opname360.core.security import hash_password
from opname360.models import Role, User, UserCreate, UserUpdate
from opname360.services import activity_log, auth


ROLE_LABELS = {
    Role.owner: 'Pemilik',
    Role.admin: 'Admin',
    Role.cashier: 'Kasir',
}


def list_users(session: Session) -> Sequence[User]:
    return session.exec(select(User).order_by(col(User.username))).all()


def get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError('Pengguna tidak ditemukan.')
    return user


def create_user(
    session: Session, user_in: UserCreate, *, actor: User | None
) -> User:
    username = user_in.username.strip().lower()
    taken = session.exec(select(User).where(User.username == username)).first()
    if taken is not None:
        raise ConflictError(f'Nama pengguna "{username}" sudah dipakai.')

    user = User(
        username=username,
        full_name=user_in.full_name.strip(),
        role=user_in.role,
        is_active=user_in.is_active,
        password_hash=hash_password(user_in.password),
    )
    session.add(user)
    session.flush()
    activity_log.record(
        session,
        actor=actor,
        action='user.create',
        summary=(
            f'Menambah pengguna {user.username} ({ROLE_LABELS[user.role]}).'
        ),
        entity_type='user',
        entity_id=user.id,
    )
    session.commit()
    session.refresh(user)
    return user


def update_user(
    session: Session, user: User, user_in: UserUpdate, *, actor: User
) -> User:
    changes = user_in.model_dump(exclude_unset=True, exclude_none=True)
    is_active_owner = user.role == Role.owner and user.is_active
    stays_active_owner = (
        changes.get('role', user.role) == Role.owner
        and changes.get('is_active', user.is_active) is True
    )
    if (
        is_active_owner
        and not stays_active_owner
        and _count_active_owners(session) <= 1
    ):
        raise ConflictError('Harus selalu ada minimal satu Pemilik aktif.')

    user.sqlmodel_update(changes)
    session.add(user)
    if not user.is_active:
        auth.end_user_sessions(session, user)
    activity_log.record(
        session,
        actor=actor,
        action='user.update',
        summary=f'Mengubah pengguna {user.username}: {_describe(changes)}.',
        entity_type='user',
        entity_id=user.id,
    )
    session.commit()
    session.refresh(user)
    return user


def reset_password(
    session: Session, user: User, password: str, *, actor: User
) -> None:
    user.password_hash = hash_password(password)
    user.failed_logins = 0
    user.locked_until = None
    session.add(user)
    auth.end_user_sessions(session, user)
    activity_log.record(
        session,
        actor=actor,
        action='user.reset_password',
        summary=f'Mengatur ulang kata sandi {user.username}.',
        entity_type='user',
        entity_id=user.id,
    )
    session.commit()


def _count_active_owners(session: Session) -> int:
    return session.exec(
        select(func.count())
        .select_from(User)
        .where(User.role == Role.owner, col(User.is_active).is_(True))
    ).one()


def _describe(changes: dict[str, object]) -> str:
    parts = []
    if 'full_name' in changes:
        parts.append(f'nama menjadi {changes["full_name"]}')
    if 'role' in changes:
        parts.append(f'peran menjadi {ROLE_LABELS[Role(changes["role"])]}')
    if 'is_active' in changes:
        parts.append('diaktifkan' if changes['is_active'] else 'dinonaktifkan')
    return ', '.join(parts) or 'tanpa perubahan'
