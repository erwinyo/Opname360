from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    CashFilter,
    ReversalCreate,
    SupplierDebt,
    SupplierPaymentCreate,
    SupplierPaymentPage,
    SupplierPaymentPublic,
)
from opname360.services import cash


router = APIRouter(
    prefix='/supplier-payments',
    tags=['supplier_payments'],
    dependencies=[Depends(require_admin)],
)

PaymentId = Annotated[int, Path(ge=1)]


@router.get('/')
def list_payments(
    session: SessionDep, filters: Annotated[CashFilter, Query()]
) -> SupplierPaymentPage:
    return cash.list_payments(session, filters)


@router.get('/debts')
def list_debts(
    session: SessionDep,
    supplier_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[SupplierDebt]:
    """Hutang Usaha: what is owed per Supplier, receipt by receipt."""
    return cash.supplier_debts(session, supplier_id)


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_payment(
    session: SessionDep, data: SupplierPaymentCreate, actor: AdminDep
) -> SupplierPaymentPublic:
    payment = cash.create_payment(session, data, actor=actor)
    return cash.payment_public(session, payment)


@router.get('/{payment_id}')
def read_payment(
    session: SessionDep, payment_id: PaymentId
) -> SupplierPaymentPublic:
    return cash.payment_public(session, cash.get_payment(session, payment_id))


@router.post('/{payment_id}/reverse')
def reverse_payment(
    session: SessionDep,
    payment_id: PaymentId,
    data: ReversalCreate,
    actor: AdminDep,
) -> SupplierPaymentPublic:
    payment = cash.get_payment(session, payment_id)
    payment = cash.reverse_payment(session, payment, data.reason, actor=actor)
    return cash.payment_public(session, payment)
