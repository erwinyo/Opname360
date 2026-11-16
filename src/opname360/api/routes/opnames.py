from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    LineResolutionSave,
    OpnameFilter,
    OpnameLineFilter,
    OpnameLinePage,
    OpnameLinePublic,
    OpnameOpen,
    OpnamePage,
    OpnamePublic,
    ReversalCreate,
    StaffOption,
    StockOpname,
    ZeroConfirm,
)
from opname360.services import opnames


router = APIRouter(
    prefix='/opnames',
    tags=['opnames'],
    dependencies=[Depends(require_admin)],
)


def get_opname_or_404(
    session: SessionDep, opname_id: Annotated[int, Path(ge=1)]
) -> StockOpname:
    return opnames.get_opname(session, opname_id)


OpnameDep = Annotated[StockOpname, Depends(get_opname_or_404)]


@router.get('/')
def list_opnames(
    session: SessionDep, filters: Annotated[OpnameFilter, Query()]
) -> OpnamePage:
    return opnames.list_opnames(session, filters)


@router.post('/', status_code=status.HTTP_201_CREATED)
def open_opname(
    session: SessionDep, admin: AdminDep, opname_in: OpnameOpen
) -> OpnamePublic:
    opname = opnames.open_opname(session, opname_in, actor=admin)
    return opnames.opname_public(session, opname, user=admin)


@router.get('/staff')
def list_staff(session: SessionDep) -> list[StaffOption]:
    """Active users, to pick Checkers and the employee of a charge."""
    return opnames.list_staff(session)


@router.get('/opening-allowed')
def opening_allowed(
    session: SessionDep, location_id: int | None = None
) -> bool:
    """Whether an Opening Opname can still be opened: only before any Stock
    Movement at the Location."""
    return opnames.opening_allowed(session, location_id)


@router.get('/{opname_id}')
def read_opname(
    session: SessionDep, admin: AdminDep, opname: OpnameDep
) -> OpnamePublic:
    return opnames.opname_public(session, opname, user=admin)


@router.get('/{opname_id}/lines')
def list_lines(
    session: SessionDep,
    admin: AdminDep,
    opname: OpnameDep,
    filters: Annotated[OpnameLineFilter, Query()],
) -> OpnameLinePage:
    return opnames.list_lines(session, opname, filters, user=admin)


@router.post('/{opname_id}/cancel')
def cancel_opname(
    session: SessionDep, admin: AdminDep, opname: OpnameDep
) -> OpnamePublic:
    opnames.cancel(session, opname, actor=admin)
    return opnames.opname_public(session, opname, user=admin)


@router.post('/{opname_id}/confirm-zero')
def confirm_zero(
    session: SessionDep,
    admin: AdminDep,
    opname: OpnameDep,
    body: ZeroConfirm,
) -> OpnamePublic:
    """Uncounted lines confirmed as none found."""
    opnames.confirm_zero(session, opname, body.line_ids, actor=admin)
    return opnames.opname_public(session, opname, user=admin)


@router.post('/{opname_id}/close-counting')
def close_counting(
    session: SessionDep, admin: AdminDep, opname: OpnameDep
) -> OpnamePublic:
    opname = opnames.close_counting(session, opname, actor=admin)
    return opnames.opname_public(session, opname, user=admin)


@router.post('/{opname_id}/lines/{line_id}/recount')
def recount_line(
    session: SessionDep,
    admin: AdminDep,
    opname: OpnameDep,
    line_id: Annotated[int, Path(ge=1)],
) -> OpnamePublic:
    line = opnames.get_line(session, opname, line_id)
    opnames.recount(session, opname, line, actor=admin)
    return opnames.opname_public(session, opname, user=admin)


@router.put('/{opname_id}/lines/{line_id}')
def save_resolution(
    session: SessionDep,
    admin: AdminDep,
    opname: OpnameDep,
    line_id: Annotated[int, Path(ge=1)],
    body: LineResolutionSave,
) -> OpnameLinePublic:
    """The approver's decision on one line."""
    line = opnames.get_line(session, opname, line_id)
    opnames.save_resolution(session, opname, line, body, actor=admin)
    return opnames.line_public(session, opname, line, user=admin)


@router.post('/{opname_id}/approve')
def approve_opname(
    session: SessionDep, admin: AdminDep, opname: OpnameDep
) -> OpnamePublic:
    opname = opnames.approve(session, opname, actor=admin)
    return opnames.opname_public(session, opname, user=admin)


@router.post('/{opname_id}/reverse')
def reverse_opname(
    session: SessionDep,
    admin: AdminDep,
    opname: OpnameDep,
    body: ReversalCreate,
) -> OpnamePublic:
    opname = opnames.reverse(session, opname, body.reason, actor=admin)
    return opnames.opname_public(session, opname, user=admin)
