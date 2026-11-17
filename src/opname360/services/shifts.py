"""Shifts: one Cashier at the one cash drawer of a Location."""

from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError, ForbiddenError, NotFoundError
from opname360.core.formatting import rupiah
from opname360.models import (
    Location,
    Role,
    Shift,
    ShiftClose,
    ShiftCurrent,
    ShiftFilter,
    ShiftOpen,
    ShiftPage,
    ShiftPublic,
    User,
)
from opname360.models._types import utc_now
from opname360.services import activity_log, documents, stock


PREFIX = 'SH'
DOCUMENT_TYPE = 'shift'


def get_shift(session: Session, shift_id: int) -> Shift:
    shift = session.get(Shift, shift_id)
    if shift is None:
        raise NotFoundError('Shift tidak ditemukan.')
    return shift


def open_shift_at(session: Session, location_id: int) -> Shift | None:
    return session.exec(
        select(Shift).where(
            Shift.location_id == location_id,
            col(Shift.closed_at).is_(None),
        )
    ).first()


def current(session: Session, user: User) -> ShiftCurrent | None:
    """The open Shift of the shop's drawer, without its cash figures."""
    shift = open_shift_at(session, stock.resolve_location(session, None))
    if shift is None:
        return None
    assert shift.id is not None
    return ShiftCurrent(
        id=shift.id,
        number=shift.number,
        cashier_id=shift.cashier_id,
        cashier_name=documents.user_name(session, shift.cashier_id) or '',
        opening_float=shift.opening_float,
        opened_at=shift.opened_at,
        is_mine=_may_use(shift, user),
    )


def selling_shift(session: Session, user: User) -> Shift:
    """The open Shift `user` sells in, locked against closing until commit
    (rule 1)."""
    shift = open_shift_at(session, stock.resolve_location(session, None))
    if shift is None:
        raise ConflictError('Buka shift dulu sebelum berjualan.')
    if not _may_use(shift, user):
        name = documents.user_name(session, shift.cashier_id)
        raise ForbiddenError(
            f'Shift {shift.number} milik {name}. Tunggu sampai ditutup.'
        )
    assert shift.id is not None
    shift = session.get(
        Shift, shift.id, with_for_update={'read': True}, populate_existing=True
    )
    assert shift is not None
    if shift.closed_at is not None:
        raise ConflictError(f'Shift {shift.number} baru saja ditutup.')
    return shift


def open_shift(session: Session, shift_in: ShiftOpen, *, actor: User) -> Shift:
    location_id = stock.resolve_location(session, None)
    # One drawer: whoever locks the Location first opens the Shift.
    session.get(Location, location_id, with_for_update=True)
    taken = open_shift_at(session, location_id)
    if taken is not None:
        name = documents.user_name(session, taken.cashier_id)
        raise ConflictError(
            f'Shift {taken.number} milik {name} masih terbuka. '
            'Tutup dulu sebelum membuka shift baru.'
        )
    assert actor.id is not None
    shift = Shift(
        number=documents.next_number(session, PREFIX),
        location_id=location_id,
        cashier_id=actor.id,
        opening_float=shift_in.opening_float,
    )
    session.add(shift)
    session.flush()
    activity_log.record(
        session,
        actor=actor,
        action='shift.open',
        summary=(
            f'Membuka shift {shift.number} dengan modal kas '
            f'{rupiah(shift.opening_float)}.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=shift.id,
    )
    session.commit()
    return shift


def close_shift(
    session: Session, shift: Shift, shift_in: ShiftClose, *, actor: User
) -> Shift:
    """The blind cash count (rule 2). All cash leaves the drawer (rule 4)."""
    assert shift.id is not None
    shift = documents.lock(session, Shift, shift.id)
    if shift.closed_at is not None:
        raise ConflictError(f'Shift {shift.number} sudah ditutup.')
    if not _may_use(shift, actor):
        raise ForbiddenError(
            'Shift hanya bisa ditutup oleh kasirnya sendiri atau Pemilik.'
        )
    shift.expected_cash = expected_cash(session, shift)
    shift.counted_cash = shift_in.counted_cash
    shift.cash_variance = shift.counted_cash - shift.expected_cash
    shift.closed_at = utc_now()
    shift.closed_by = actor.id
    session.add(shift)
    variance = shift.cash_variance
    activity_log.record(
        session,
        actor=actor,
        action='shift.close',
        summary=(
            f'Menutup shift {shift.number}: kas dihitung '
            f'{rupiah(shift.counted_cash)}, '
            + (
                'sesuai.'
                if variance == 0
                else f'selisih {"lebih" if variance > 0 else "kurang"} '
                f'{rupiah(abs(variance))}.'
            )
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=shift.id,
    )
    session.commit()
    return shift


def expected_cash(session: Session, shift: Shift) -> int:
    """Float plus cash taken minus cash given back."""
    if shift.expected_cash is not None:
        return shift.expected_cash
    return shift.opening_float


def needs_resolution(shift: Shift) -> bool:
    """A short drawer waits for the Owner (rule 3)."""
    return (
        shift.cash_variance is not None
        and shift.cash_variance < 0
        and shift.resolution is None
    )


def list_shifts(session: Session, filters: ShiftFilter) -> ShiftPage:
    query = select(Shift)
    if filters.needs_resolution:
        query = query.where(
            col(Shift.cash_variance) < 0, col(Shift.resolution).is_(None)
        )
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    shifts = session.exec(
        query.order_by(col(Shift.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return ShiftPage(
        items=[shift_public(session, shift) for shift in shifts], total=total
    )


def shift_public(session: Session, shift: Shift) -> ShiftPublic:
    location = session.get(Location, shift.location_id)
    assert location is not None
    return ShiftPublic.model_validate(
        shift,
        update={
            'location_name': location.name,
            'cashier_name': documents.user_name(session, shift.cashier_id)
            or '',
            'closed_by_name': documents.user_name(session, shift.closed_by),
            'expected_cash': expected_cash(session, shift),
            'needs_resolution': needs_resolution(shift),
            'charged_user_name': documents.user_name(
                session, shift.charged_user_id
            ),
            'resolved_by_name': documents.user_name(
                session, shift.resolved_by
            ),
        },
    )


def may_read(shift: Shift, user: User) -> bool:
    """The back office always; the Cashier only their own closed Shift, so
    the count stays blind."""
    if user.role in (Role.owner, Role.admin):
        return True
    return shift.cashier_id == user.id and shift.closed_at is not None


def _may_use(shift: Shift, user: User) -> bool:
    return shift.cashier_id == user.id or user.role == Role.owner
