"""The Checker's phone. Any role can be a Checker; the service checks the
assignment."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import CurrentUserDep, SessionDep, get_current_user
from opname360.models import (
    CountCreate,
    CountSheet,
    CountSkuOption,
    CountingSummary,
    MyCountEntry,
    StockOpname,
)
from opname360.services import opnames


router = APIRouter(
    prefix='/counting',
    tags=['counting'],
    dependencies=[Depends(get_current_user)],
)


def get_opname_or_404(
    session: SessionDep, opname_id: Annotated[int, Path(ge=1)]
) -> StockOpname:
    return opnames.get_opname(session, opname_id)


OpnameDep = Annotated[StockOpname, Depends(get_opname_or_404)]


@router.get('/')
def list_sessions(
    session: SessionDep, user: CurrentUserDep
) -> list[CountingSummary]:
    """Unfinished sessions the signed-in user counts in."""
    return opnames.counting_sessions(session, user)


@router.get('/{opname_id}')
def read_sheet(
    session: SessionDep, user: CurrentUserDep, opname: OpnameDep
) -> CountSheet:
    return opnames.count_sheet(session, opname, user=user)


@router.get('/{opname_id}/skus')
def find_skus(
    session: SessionDep,
    user: CurrentUserDep,
    opname: OpnameDep,
    search: Annotated[str, Query(max_length=100)],
) -> list[CountSkuOption]:
    return opnames.find_skus(session, opname, search, user=user)


@router.post('/{opname_id}/entries', status_code=status.HTTP_201_CREATED)
def add_count(
    session: SessionDep,
    user: CurrentUserDep,
    opname: OpnameDep,
    count_in: CountCreate,
) -> MyCountEntry:
    return opnames.add_count(session, opname, count_in, user=user)


@router.delete(
    '/{opname_id}/entries/{entry_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_count(
    session: SessionDep,
    user: CurrentUserDep,
    opname: OpnameDep,
    entry_id: Annotated[int, Path(ge=1)],
) -> None:
    opnames.cancel_count(session, opname, entry_id, user=user)
