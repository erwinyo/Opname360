from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    Supplier,
    SupplierCreate,
    SupplierPublic,
    SupplierUpdate,
)
from opname360.services import suppliers as suppliers_service


router = APIRouter(
    prefix='/suppliers',
    tags=['suppliers'],
    dependencies=[Depends(require_admin)],
)


def get_supplier_or_404(
    session: SessionDep, supplier_id: Annotated[int, Path(ge=1)]
) -> Supplier:
    return suppliers_service.get_supplier(session, supplier_id)


SupplierDep = Annotated[Supplier, Depends(get_supplier_or_404)]


@router.get('/', response_model=list[SupplierPublic])
def list_suppliers(session: SessionDep) -> Sequence[Supplier]:
    return suppliers_service.list_suppliers(session)


@router.post(
    '/', response_model=SupplierPublic, status_code=status.HTTP_201_CREATED
)
def create_supplier(
    session: SessionDep, admin: AdminDep, supplier_in: SupplierCreate
) -> Supplier:
    return suppliers_service.create_supplier(session, supplier_in, actor=admin)


@router.patch('/{supplier_id}', response_model=SupplierPublic)
def update_supplier(
    session: SessionDep,
    admin: AdminDep,
    supplier: SupplierDep,
    supplier_in: SupplierUpdate,
) -> Supplier:
    return suppliers_service.update_supplier(
        session, supplier, supplier_in, actor=admin
    )
