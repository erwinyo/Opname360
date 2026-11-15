from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    ReversalCreate,
    SupplierReturn,
    SupplierReturnFilter,
    SupplierReturnPage,
    SupplierReturnPublic,
    SupplierReturnSave,
)
from opname360.services import supplier_returns as returns


router = APIRouter(
    prefix='/supplier-returns',
    tags=['supplier_returns'],
    dependencies=[Depends(require_admin)],
)


def get_return_or_404(
    session: SessionDep, return_id: Annotated[int, Path(ge=1)]
) -> SupplierReturn:
    return returns.get_return(session, return_id)


ReturnDep = Annotated[SupplierReturn, Depends(get_return_or_404)]


@router.get('/')
def list_returns(
    session: SessionDep, filters: Annotated[SupplierReturnFilter, Query()]
) -> SupplierReturnPage:
    return returns.list_returns(session, filters)


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_return(
    session: SessionDep, admin: AdminDep, return_in: SupplierReturnSave
) -> SupplierReturnPublic:
    supplier_return = returns.create_draft(session, return_in, actor=admin)
    return returns.return_public(session, supplier_return)


@router.get('/{return_id}')
def read_return(
    session: SessionDep, supplier_return: ReturnDep
) -> SupplierReturnPublic:
    return returns.return_public(session, supplier_return)


@router.put('/{return_id}')
def update_return(
    session: SessionDep,
    admin: AdminDep,
    supplier_return: ReturnDep,
    return_in: SupplierReturnSave,
) -> SupplierReturnPublic:
    returns.update_draft(session, supplier_return, return_in, actor=admin)
    return returns.return_public(session, supplier_return)


@router.delete('/{return_id}', status_code=status.HTTP_204_NO_CONTENT)
def discard_return(
    session: SessionDep, admin: AdminDep, supplier_return: ReturnDep
) -> None:
    returns.discard_draft(session, supplier_return, actor=admin)


@router.post('/{return_id}/complete')
def complete_return(
    session: SessionDep, admin: AdminDep, supplier_return: ReturnDep
) -> SupplierReturnPublic:
    supplier_return = returns.complete(session, supplier_return, actor=admin)
    return returns.return_public(session, supplier_return)


@router.post('/{return_id}/reverse')
def reverse_return(
    session: SessionDep,
    admin: AdminDep,
    supplier_return: ReturnDep,
    body: ReversalCreate,
) -> SupplierReturnPublic:
    supplier_return = returns.reverse(
        session, supplier_return, body.reason, actor=admin
    )
    return returns.return_public(session, supplier_return)
