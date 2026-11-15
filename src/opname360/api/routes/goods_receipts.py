from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    GoodsReceipt,
    GoodsReceiptFilter,
    GoodsReceiptPage,
    GoodsReceiptPublic,
    GoodsReceiptSave,
)
from opname360.services import goods_receipts as receipts


router = APIRouter(
    prefix='/goods-receipts',
    tags=['goods_receipts'],
    dependencies=[Depends(require_admin)],
)


def get_receipt_or_404(
    session: SessionDep, receipt_id: Annotated[int, Path(ge=1)]
) -> GoodsReceipt:
    return receipts.get_receipt(session, receipt_id)


ReceiptDep = Annotated[GoodsReceipt, Depends(get_receipt_or_404)]


@router.get('/')
def list_receipts(
    session: SessionDep, filters: Annotated[GoodsReceiptFilter, Query()]
) -> GoodsReceiptPage:
    return receipts.list_receipts(session, filters)


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_receipt(
    session: SessionDep, admin: AdminDep, receipt_in: GoodsReceiptSave
) -> GoodsReceiptPublic:
    receipt = receipts.create_draft(session, receipt_in, actor=admin)
    return receipts.receipt_public(session, receipt)


@router.get('/{receipt_id}')
def read_receipt(
    session: SessionDep, receipt: ReceiptDep
) -> GoodsReceiptPublic:
    return receipts.receipt_public(session, receipt)


@router.put('/{receipt_id}')
def update_receipt(
    session: SessionDep,
    admin: AdminDep,
    receipt: ReceiptDep,
    receipt_in: GoodsReceiptSave,
) -> GoodsReceiptPublic:
    receipts.update_draft(session, receipt, receipt_in, actor=admin)
    return receipts.receipt_public(session, receipt)


@router.delete('/{receipt_id}', status_code=status.HTTP_204_NO_CONTENT)
def discard_receipt(
    session: SessionDep, admin: AdminDep, receipt: ReceiptDep
) -> None:
    receipts.discard_draft(session, receipt, actor=admin)


@router.post('/{receipt_id}/complete')
def complete_receipt(
    session: SessionDep, admin: AdminDep, receipt: ReceiptDep
) -> GoodsReceiptPublic:
    receipt = receipts.complete(session, receipt, actor=admin)
    return receipts.receipt_public(session, receipt)
