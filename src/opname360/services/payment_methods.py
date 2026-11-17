from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from opname360.core.errors import AppError, ConflictError, NotFoundError
from opname360.models import (
    PaymentMethod,
    PaymentMethodCreate,
    PaymentMethodUpdate,
    User,
)
from opname360.services import activity_log, ledger


def list_methods(
    session: Session, *, active_only: bool = False
) -> Sequence[PaymentMethod]:
    query = select(PaymentMethod).order_by(
        col(PaymentMethod.is_cash).desc(), col(PaymentMethod.id)
    )
    if active_only:
        query = query.where(col(PaymentMethod.is_active).is_(True))
    return session.exec(query).all()


def get_method(session: Session, method_id: int) -> PaymentMethod:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise NotFoundError('Metode pembayaran tidak ditemukan.')
    return method


def cash_method(session: Session) -> PaymentMethod:
    """Where change and refunds come from unless the Cashier picks another."""
    method = session.exec(
        select(PaymentMethod)
        .where(
            col(PaymentMethod.is_cash).is_(True),
            col(PaymentMethod.is_active).is_(True),
        )
        .order_by(col(PaymentMethod.id))
    ).first()
    if method is None:
        raise ConflictError('Belum ada metode pembayaran tunai yang aktif.')
    return method


def create_method(
    session: Session, method_in: PaymentMethodCreate, *, actor: User
) -> PaymentMethod:
    method = PaymentMethod(
        name=_checked_name(session, method_in.name),
        is_cash=method_in.is_cash,
        is_active=method_in.is_active,
    )
    session.add(method)
    session.flush()
    activity_log.record(
        session,
        actor=actor,
        action='payment_method.create',
        summary=f'Menambah metode pembayaran {method.name}.',
        entity_type='payment_method',
        entity_id=method.id,
    )
    session.commit()
    return method


def update_method(
    session: Session,
    method: PaymentMethod,
    method_in: PaymentMethodUpdate,
    *,
    actor: User,
) -> PaymentMethod:
    sent = method_in.model_dump(exclude_unset=True)
    if sent.get('name') is not None:
        method.name = _checked_name(session, sent['name'], exclude=method)
    if sent.get('is_active') is False and method.is_cash and method.is_active:
        _keep_one_cash_method(session, method)
    if sent.get('is_active') is not None:
        method.is_active = sent['is_active']
    if 'account_id' in sent:
        if method.is_cash:
            raise ConflictError('Uang tunai selalu masuk ke Kas Kasir.')
        method.account_id = (
            None
            if sent['account_id'] is None
            else ledger.paying_account(session, sent['account_id'])
        )
    session.add(method)
    activity_log.record(
        session,
        actor=actor,
        action='payment_method.update',
        summary=(
            f'Mengubah metode pembayaran {method.name}'
            + ('' if method.is_active else ' (nonaktif)')
            + '.'
        ),
        entity_type='payment_method',
        entity_id=method.id,
    )
    session.commit()
    return method


def _keep_one_cash_method(session: Session, method: PaymentMethod) -> None:
    """Change and refunds need cash: the last cash method stays active."""
    others = session.exec(
        select(func.count()).where(
            col(PaymentMethod.is_cash).is_(True),
            col(PaymentMethod.is_active).is_(True),
            PaymentMethod.id != method.id,
        )
    ).one()
    if not others:
        raise ConflictError(
            f'{method.name} adalah satu-satunya metode tunai yang aktif; '
            'kembalian dan refund dibayar dari situ.'
        )


def _checked_name(
    session: Session, name: str, *, exclude: PaymentMethod | None = None
) -> str:
    name = name.strip()
    if not name:
        raise AppError('Nama metode pembayaran wajib diisi.')
    query = select(PaymentMethod.id).where(
        func.lower(PaymentMethod.name) == name.lower()
    )
    if exclude is not None:
        query = query.where(PaymentMethod.id != exclude.id)
    if session.exec(query).first() is not None:
        raise ConflictError(f'Metode pembayaran "{name}" sudah ada.')
    return name
