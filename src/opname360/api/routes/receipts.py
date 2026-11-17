from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import (
    CurrentUserDep,
    SellerDep,
    SessionDep,
    get_current_user,
)
from opname360.core.errors import ForbiddenError
from opname360.models import (
    Cart,
    Quote,
    Receipt,
    ReceiptCreate,
    ReceiptFilter,
    ReceiptPage,
    ReceiptPublic,
    ReceiptVoid,
    Role,
    TillSku,
)
from opname360.services import receipts, shifts


router = APIRouter(
    prefix='/receipts',
    tags=['receipts'],
    dependencies=[Depends(get_current_user)],
)


def get_receipt_or_404(
    session: SessionDep, receipt_id: Annotated[int, Path(ge=1)]
) -> Receipt:
    return receipts.get_receipt(session, receipt_id)


ReceiptDep = Annotated[Receipt, Depends(get_receipt_or_404)]


@router.get('/')
def list_receipts(
    session: SessionDep,
    user: CurrentUserDep,
    filters: Annotated[ReceiptFilter, Query()],
) -> ReceiptPage:
    """One Shift's Receipts. A Cashier sees only their own Shifts."""
    shift = shifts.get_shift(session, filters.shift_id)
    if user.role == Role.cashier and shift.cashier_id != user.id:
        raise ForbiddenError('Itu transaksi shift kasir lain.')
    return receipts.list_receipts(session, filters)


@router.get('/skus')
def find_skus(
    session: SessionDep,
    seller: SellerDep,
    search: Annotated[str, Query(max_length=100)],
) -> list[TillSku]:
    return receipts.find_skus(session, search)


@router.get('/for-return')
def receipt_for_return(
    session: SessionDep,
    seller: SellerDep,
    number: Annotated[str, Query(min_length=1, max_length=30)],
) -> ReceiptPublic:
    """A Receipt scanned for a return or exchange, if it can still be
    returned."""
    receipt = receipts.receipt_for_return(session, number)
    return receipts.receipt_public(session, receipt)


@router.post('/quote')
def quote(session: SessionDep, seller: SellerDep, cart: Cart) -> Quote:
    """Today's prices and Promotions for a cart, before payment."""
    return receipts.quote(session, cart)


@router.post('/', status_code=status.HTTP_201_CREATED)
def complete_receipt(
    session: SessionDep, seller: SellerDep, receipt_in: ReceiptCreate
) -> ReceiptPublic:
    receipt = receipts.complete(session, receipt_in, actor=seller)
    return receipts.receipt_public(session, receipt)


@router.get('/{receipt_id}')
def read_receipt(session: SessionDep, receipt: ReceiptDep) -> ReceiptPublic:
    return receipts.receipt_public(session, receipt)


@router.post('/{receipt_id}/print')
def print_receipt(
    session: SessionDep, seller: SellerDep, receipt: ReceiptDep
) -> ReceiptPublic:
    """Count a printout; from the second one on it says it is a copy."""
    receipt = receipts.print_receipt(session, receipt, actor=seller)
    return receipts.receipt_public(session, receipt)


@router.post('/{receipt_id}/void')
def void_receipt(
    session: SessionDep,
    seller: SellerDep,
    receipt: ReceiptDep,
    body: ReceiptVoid,
) -> ReceiptPublic:
    """Cancel a Receipt while its Shift is still open."""
    receipt = receipts.void(session, receipt, body.reason, actor=seller)
    return receipts.receipt_public(session, receipt)
