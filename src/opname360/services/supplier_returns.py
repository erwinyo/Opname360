from decimal import Decimal

from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError, NotFoundError
from opname360.core.formatting import rupiah, sku_label
from opname360.models import (
    DocumentStatus,
    GoodsReceipt,
    GoodsReceiptLine,
    Location,
    MovementReason,
    Sku,
    Supplier,
    SupplierReturn,
    SupplierReturnFilter,
    SupplierReturnLine,
    SupplierReturnLinePublic,
    SupplierReturnPage,
    SupplierReturnPublic,
    SupplierReturnSave,
    SupplierReturnSummary,
    User,
)
from opname360.models._types import utc_now
from opname360.services import (
    activity_log,
    costing,
    documents,
    goods_receipts,
    posting,
)


PREFIX = 'RB'  # Retur Beli
DOCUMENT_TYPE = 'supplier_return'


def list_returns(
    session: Session, filters: SupplierReturnFilter
) -> SupplierReturnPage:
    query = (
        select(SupplierReturn, Supplier.name, GoodsReceipt.number)
        .join(Supplier, col(SupplierReturn.supplier_id) == Supplier.id)
        .join(
            GoodsReceipt,
            col(SupplierReturn.goods_receipt_id) == GoodsReceipt.id,
        )
    )
    if filters.status is not None:
        query = query.where(SupplierReturn.status == filters.status)
    if filters.goods_receipt_id is not None:
        query = query.where(
            SupplierReturn.goods_receipt_id == filters.goods_receipt_id
        )
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    rows = session.exec(
        query.order_by(col(SupplierReturn.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    line_counts = dict(
        session.exec(
            select(SupplierReturnLine.return_id, func.count())
            .where(
                col(SupplierReturnLine.return_id).in_(
                    [supplier_return.id for supplier_return, _, _ in rows]
                )
            )
            .group_by(col(SupplierReturnLine.return_id))
        ).all()
    )
    return SupplierReturnPage(
        items=[
            SupplierReturnSummary.model_validate(
                supplier_return,
                update={
                    'supplier_name': supplier_name,
                    'goods_receipt_number': receipt_number,
                    'line_count': line_counts.get(supplier_return.id, 0),
                },
            )
            for supplier_return, supplier_name, receipt_number in rows
        ],
        total=total,
    )


def get_return(session: Session, return_id: int) -> SupplierReturn:
    supplier_return = session.get(SupplierReturn, return_id)
    if supplier_return is None:
        raise NotFoundError('Retur pembelian tidak ditemukan.')
    return supplier_return


def return_public(
    session: Session, supplier_return: SupplierReturn
) -> SupplierReturnPublic:
    receipt = session.get(GoodsReceipt, supplier_return.goods_receipt_id)
    supplier = session.get(Supplier, supplier_return.supplier_id)
    location = session.get(Location, supplier_return.location_id)
    assert receipt is not None
    assert supplier is not None
    assert location is not None
    lines = []
    for line in supplier_return.lines:
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        lines.append(
            SupplierReturnLinePublic.model_validate(
                line,
                update={
                    'product_name': sku.product.name,
                    'size': sku.size,
                    'color': sku.color,
                    'code': sku.code,
                    'barcode': sku.barcode,
                    'stock_unit': sku.stock_unit,
                },
            )
        )
    return SupplierReturnPublic.model_validate(
        supplier_return,
        update={
            'goods_receipt_number': receipt.number,
            'supplier_name': supplier.name,
            'location_name': location.name,
            'created_by_name': documents.user_name(
                session, supplier_return.created_by
            ),
            'completed_by_name': documents.user_name(
                session, supplier_return.completed_by
            ),
            'reversal': documents.reversal_public(
                session, DOCUMENT_TYPE, supplier_return.id
            ),
            'lines': lines,
        },
    )


def create_draft(
    session: Session, return_in: SupplierReturnSave, *, actor: User
) -> SupplierReturn:
    receipt = _returnable_receipt(session, return_in.goods_receipt_id)
    supplier_return = SupplierReturn(
        goods_receipt_id=return_in.goods_receipt_id,
        supplier_id=receipt.supplier_id,
        location_id=receipt.location_id,
        returned_on=return_in.returned_on,
        created_by=actor.id,
    )
    _apply(session, supplier_return, receipt, return_in)
    activity_log.record(
        session,
        actor=actor,
        action='supplier_return.create',
        summary=f'Membuat draf retur pembelian untuk {receipt.number}.',
        entity_type=DOCUMENT_TYPE,
        entity_id=supplier_return.id,
    )
    session.commit()
    return supplier_return


def update_draft(
    session: Session,
    supplier_return: SupplierReturn,
    return_in: SupplierReturnSave,
    *,
    actor: User,
) -> SupplierReturn:
    _require_draft(supplier_return)
    if return_in.goods_receipt_id != supplier_return.goods_receipt_id:
        raise ConflictError(
            'Barang masuk asal retur tidak bisa diganti. Buat retur baru.'
        )
    receipt = _returnable_receipt(session, return_in.goods_receipt_id)
    _apply(session, supplier_return, receipt, return_in)
    session.commit()
    return supplier_return


def discard_draft(
    session: Session, supplier_return: SupplierReturn, *, actor: User
) -> None:
    _require_draft(supplier_return)
    activity_log.record(
        session,
        actor=actor,
        action='supplier_return.discard',
        summary='Membuang draf retur pembelian.',
        entity_type=DOCUMENT_TYPE,
        entity_id=supplier_return.id,
    )
    session.delete(supplier_return)
    session.commit()


def complete(
    session: Session, supplier_return: SupplierReturn, *, actor: User
) -> SupplierReturn:
    assert supplier_return.id is not None
    supplier_return = documents.lock(
        session, SupplierReturn, supplier_return.id
    )
    _require_draft(supplier_return)
    assert supplier_return.id is not None
    if not supplier_return.lines:
        raise ConflictError('Retur pembelian belum punya isi.')
    # Lock the receipt too: two returns from it can't both take the last units.
    receipt = documents.lock(
        session, GoodsReceipt, supplier_return.goods_receipt_id
    )
    if receipt.status != DocumentStatus.completed:
        raise ConflictError(
            f'Barang masuk {receipt.number} sudah dibatalkan; '
            'barangnya tidak bisa diretur.'
        )
    _check_quantities(session, receipt, supplier_return.lines)

    supplier_return.number = documents.next_number(session, PREFIX)
    supplier_return.status = DocumentStatus.completed
    supplier_return.completed_by = actor.id
    supplier_return.completed_at = utc_now()
    session.add(supplier_return)

    source = costing.Source(
        DOCUMENT_TYPE, supplier_return.id, supplier_return.number
    )
    for line in sorted(supplier_return.lines, key=lambda line: line.sku_id):
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        movement = costing.issue(
            session,
            sku=sku,
            location_id=supplier_return.location_id,
            quantity=line.quantity,
            reason=MovementReason.supplier_return,
            source=source,
            actor=actor,
        )
        line.stock_cost = -movement.value
        session.add(line)
    supplier = session.get(Supplier, supplier_return.supplier_id)
    assert supplier is not None
    activity_log.record(
        session,
        actor=actor,
        action='supplier_return.complete',
        summary=(
            f'Menyelesaikan retur pembelian {supplier_return.number} ke '
            f'{supplier.name} dari {receipt.number}: '
            f'{rupiah(round(supplier_return.total_refund))}.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=supplier_return.id,
    )
    posting.supplier_return(session, supplier_return, actor=actor)
    session.commit()
    return supplier_return


def reverse(
    session: Session,
    supplier_return: SupplierReturn,
    reason: str,
    *,
    actor: User,
) -> SupplierReturn:
    assert supplier_return.id is not None
    supplier_return = documents.lock(
        session, SupplierReturn, supplier_return.id
    )
    documents.reverse(
        session,
        supplier_return,
        document_type=DOCUMENT_TYPE,
        label=f'retur pembelian {supplier_return.number}',
        reason=reason,
        actor=actor,
    )
    session.commit()
    return supplier_return


def _returnable_receipt(session: Session, receipt_id: int) -> GoodsReceipt:
    receipt = goods_receipts.get_receipt(session, receipt_id)
    if receipt.status != DocumentStatus.completed:
        raise ConflictError(
            'Hanya barang masuk yang sudah selesai yang bisa diretur.'
        )
    return receipt


def _apply(
    session: Session,
    supplier_return: SupplierReturn,
    receipt: GoodsReceipt,
    return_in: SupplierReturnSave,
) -> None:
    supplier_return.returned_on = return_in.returned_on
    supplier_return.note = (return_in.note or '').strip() or None
    for line in list(supplier_return.lines):
        session.delete(line)
    session.add(supplier_return)
    session.flush()
    assert supplier_return.id is not None

    receipt_lines = {line.id: line for line in receipt.lines}
    seen = set()
    total = Decimal(0)
    for row in return_in.lines:
        receipt_line = receipt_lines.get(row.goods_receipt_line_id)
        if receipt_line is None:
            raise NotFoundError(
                f'Baris itu bukan bagian dari barang masuk {receipt.number}.'
            )
        if row.goods_receipt_line_id in seen:
            raise ConflictError('Satu baris barang masuk muncul dua kali.')
        seen.add(row.goods_receipt_line_id)
        line = SupplierReturnLine(
            return_id=supplier_return.id,
            goods_receipt_line_id=row.goods_receipt_line_id,
            sku_id=receipt_line.sku_id,
            quantity=row.quantity,
            unit_cost=receipt_line.unit_cost,
            total_refund=costing.money(row.quantity * receipt_line.unit_cost),
        )
        total += line.total_refund
        session.add(line)
    supplier_return.total_refund = total
    session.flush()
    session.refresh(supplier_return)
    _check_quantities(session, receipt, supplier_return.lines)


def _check_quantities(
    session: Session,
    receipt: GoodsReceipt,
    lines: list[SupplierReturnLine],
) -> None:
    """Rule 9: no more than the receipt brought in, minus earlier returns."""
    returned = goods_receipts.returned_quantities(session, receipt)
    receipt_lines: dict[int | None, GoodsReceiptLine] = {
        line.id: line for line in receipt.lines
    }
    for line in lines:
        receipt_line = receipt_lines[line.goods_receipt_line_id]
        left = receipt_line.quantity - returned.get(
            line.goods_receipt_line_id, Decimal(0)
        )
        if line.quantity > left:
            sku = session.get(Sku, line.sku_id)
            assert sku is not None
            label = sku_label(sku.product.name, sku.size, sku.color)
            raise ConflictError(
                f'{label}: paling banyak {left.normalize():f} {sku.stock_unit} '
                f'yang masih bisa diretur dari {receipt.number}.'
            )


def _require_draft(supplier_return: SupplierReturn) -> None:
    if supplier_return.status != DocumentStatus.draft:
        raise ConflictError(
            f'Retur pembelian {supplier_return.number} sudah diselesaikan '
            'dan tidak bisa diubah.'
        )
