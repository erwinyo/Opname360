from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    CashFilter,
    CashOutCreate,
    CashOutPage,
    CashOutPublic,
    CashTransferCreate,
    CashTransferPage,
    CashTransferPublic,
    ReversalCreate,
)
from opname360.services import cash


# Rule 15: the Owner and the Admin record money; a Cashier doesn't.
router = APIRouter(
    prefix='/cash', tags=['cash'], dependencies=[Depends(require_admin)]
)

DocumentId = Annotated[int, Path(ge=1)]


@router.get('/outs')
def list_cash_outs(
    session: SessionDep, filters: Annotated[CashFilter, Query()]
) -> CashOutPage:
    return cash.list_cash_outs(session, filters)


@router.post('/outs', status_code=status.HTTP_201_CREATED)
def create_cash_out(
    session: SessionDep, data: CashOutCreate, actor: AdminDep
) -> CashOutPublic:
    cash_out = cash.create_cash_out(session, data, actor=actor)
    return cash.cash_out_public(session, cash_out)


@router.get('/outs/{cash_out_id}')
def read_cash_out(
    session: SessionDep, cash_out_id: DocumentId
) -> CashOutPublic:
    return cash.cash_out_public(
        session, cash.get_cash_out(session, cash_out_id)
    )


@router.post('/outs/{cash_out_id}/reverse')
def reverse_cash_out(
    session: SessionDep,
    cash_out_id: DocumentId,
    data: ReversalCreate,
    actor: AdminDep,
) -> CashOutPublic:
    cash_out = cash.get_cash_out(session, cash_out_id)
    cash_out = cash.reverse_cash_out(
        session, cash_out, data.reason, actor=actor
    )
    return cash.cash_out_public(session, cash_out)


@router.get('/transfers')
def list_transfers(
    session: SessionDep, filters: Annotated[CashFilter, Query()]
) -> CashTransferPage:
    return cash.list_transfers(session, filters)


@router.post('/transfers', status_code=status.HTTP_201_CREATED)
def create_transfer(
    session: SessionDep, data: CashTransferCreate, actor: AdminDep
) -> CashTransferPublic:
    transfer = cash.create_transfer(session, data, actor=actor)
    return cash.transfer_public(session, transfer)


@router.get('/transfers/{transfer_id}')
def read_transfer(
    session: SessionDep, transfer_id: DocumentId
) -> CashTransferPublic:
    return cash.transfer_public(
        session, cash.get_transfer(session, transfer_id)
    )


@router.post('/transfers/{transfer_id}/reverse')
def reverse_transfer(
    session: SessionDep,
    transfer_id: DocumentId,
    data: ReversalCreate,
    actor: AdminDep,
) -> CashTransferPublic:
    transfer = cash.get_transfer(session, transfer_id)
    transfer = cash.reverse_transfer(
        session, transfer, data.reason, actor=actor
    )
    return cash.transfer_public(session, transfer)
