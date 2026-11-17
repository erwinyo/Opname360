from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import (
    AdminDep,
    CurrentUserDep,
    SellerDep,
    SessionDep,
    get_current_user,
)
from opname360.core.errors import ForbiddenError
from opname360.models import (
    Shift,
    ShiftClose,
    ShiftCurrent,
    ShiftFilter,
    ShiftOpen,
    ShiftPage,
    ShiftPublic,
)
from opname360.services import shifts


router = APIRouter(
    prefix='/shifts',
    tags=['shifts'],
    dependencies=[Depends(get_current_user)],
)


def get_shift_or_404(
    session: SessionDep, shift_id: Annotated[int, Path(ge=1)]
) -> Shift:
    return shifts.get_shift(session, shift_id)


ShiftDep = Annotated[Shift, Depends(get_shift_or_404)]


@router.get('/current')
def read_current(
    session: SessionDep, seller: SellerDep
) -> ShiftCurrent | None:
    """The drawer's open Shift, if any. No cash figures: the count is blind."""
    return shifts.current(session, seller)


@router.post('/', status_code=status.HTTP_201_CREATED)
def open_shift(
    session: SessionDep, seller: SellerDep, shift_in: ShiftOpen
) -> ShiftCurrent:
    shifts.open_shift(session, shift_in, actor=seller)
    current = shifts.current(session, seller)
    assert current is not None
    return current


@router.post('/{shift_id}/close')
def close_shift(
    session: SessionDep,
    seller: SellerDep,
    shift: ShiftDep,
    shift_in: ShiftClose,
) -> ShiftPublic:
    shift = shifts.close_shift(session, shift, shift_in, actor=seller)
    return shifts.shift_public(session, shift)


@router.get('/')
def list_shifts(
    session: SessionDep,
    admin: AdminDep,
    filters: Annotated[ShiftFilter, Query()],
) -> ShiftPage:
    return shifts.list_shifts(session, filters)


@router.get('/{shift_id}')
def read_shift(
    session: SessionDep, user: CurrentUserDep, shift: ShiftDep
) -> ShiftPublic:
    if not shifts.may_read(shift, user):
        raise ForbiddenError('Ringkasan shift terlihat setelah shift ditutup.')
    return shifts.shift_public(session, shift)
