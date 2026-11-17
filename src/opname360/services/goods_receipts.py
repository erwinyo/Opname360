from decimal import Decimal

from sqlmodel import Session, col, func, select

from opname360.core.errors import AppError, ConflictError, NotFoundError
from opname360.core.formatting import rupiah, sku_label
from opname360.models import (
    DocumentStatus,
    GoodsReceipt,
    GoodsReceiptFilter,
    GoodsReceiptLine,
    GoodsReceiptLinePublic,
    GoodsReceiptPage,
    GoodsReceiptPublic,
    GoodsReceiptSave,
    GoodsReceiptSummary,
    Location,
    MovementReason,
    PaymentStatus,
    Sku,
    Supplier,
    SupplierReturn,
    SupplierReturnLine,
    User,
)
from opname360.models._types import utc_now
from opname360.services import (
    activity_log,
    costing,
    documents,
    ledger,
    posting,
    stock,
    suppliers,
)


PREFIX = 'BM'  # Barang Masuk
DOCUMENT_TYPE = 'goods_receipt'


def list_receipts(
    session: Session, filters: GoodsReceiptFilter
) -> GoodsReceiptPage:
    query = select(GoodsReceipt, Supplier.name).join(Supplier)
    if filters.status is not None:
        query = query.where(GoodsReceipt.status == filters.status)
    if filters.supplier_id is not None:
        query = query.where(GoodsReceipt.supplier_id == filters.supplier_id)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    rows = session.exec(
        query.order_by(col(GoodsReceipt.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    line_counts = dict(
        session.exec(
            select(GoodsReceiptLine.receipt_id, func.count())
            .where(
                col(GoodsReceiptLine.receipt_id).in_(
                    [receipt.id for receipt, _ in rows]
                )
            )
            .group_by(col(GoodsReceiptLine.receipt_id))
        ).all()
    )
    return GoodsReceiptPage(
        items=[
            GoodsReceiptSummary.model_validate(
                receipt,
                update={
                    'supplier_name': supplier_name,
                    'line_count': line_counts.get(receipt.id, 0),
                },
            )
            for receipt, supplier_name in rows
        ],
        total=total,
    )


def get_receipt(session: Session, receipt_id: int) -> GoodsReceipt:
    receipt = session.get(GoodsReceipt, receipt_id)
    if receipt is None:
        raise NotFoundError('Barang masuk tidak ditemukan.')
    return receipt


def receipt_public(
    session: Session, receipt: GoodsReceipt
) -> GoodsReceiptPublic:
    supplier = suppliers.get_supplier(session, receipt.supplier_id)
    location = session.get(Location, receipt.location_id)
    assert location is not None
    returned = returned_quantities(session, receipt)
    lines = []
    for line in receipt.lines:
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        lines.append(
            GoodsReceiptLinePublic.model_validate(
                line,
                update={
                    'product_name': sku.product.name,
                    'size': sku.size,
                    'color': sku.color,
                    'code': sku.code,
                    'barcode': sku.barcode,
                    'stock_unit': sku.stock_unit,
                    'returned_quantity': returned.get(
                        line.id or 0, Decimal(0)
                    ),
                    'purchase_pack_name': sku.purchase_pack_name,
                    'purchase_pack_size': sku.purchase_pack_size,
                },
            )
        )
    return GoodsReceiptPublic.model_validate(
        receipt,
        update={
            'supplier_name': supplier.name,
            'location_name': location.name,
            'created_by_name': documents.user_name(
                session, receipt.created_by
            ),
            'completed_by_name': documents.user_name(
                session, receipt.completed_by
            ),
            'reversal': documents.reversal_public(
                session, DOCUMENT_TYPE, receipt.id
            ),
            'paid_from_name': ledger.account_name(
                session, receipt.paid_from_account_id
            ),
            'lines': lines,
        },
    )


def create_draft(
    session: Session, receipt_in: GoodsReceiptSave, *, actor: User
) -> GoodsReceipt:
    supplier = _usable_supplier(session, receipt_in.supplier_id)
    receipt = GoodsReceipt(
        supplier_id=receipt_in.supplier_id,
        location_id=stock.resolve_location(session, receipt_in.location_id),
        received_on=receipt_in.received_on,
        payment_status=receipt_in.payment_status,
        created_by=actor.id,
    )
    _apply(session, receipt, receipt_in)
    activity_log.record(
        session,
        actor=actor,
        action='goods_receipt.create',
        summary=f'Membuat draf barang masuk dari {supplier.name}.',
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    session.commit()
    return receipt


def update_draft(
    session: Session,
    receipt: GoodsReceipt,
    receipt_in: GoodsReceiptSave,
    *,
    actor: User,
) -> GoodsReceipt:
    _require_draft(receipt)
    _usable_supplier(session, receipt_in.supplier_id)
    receipt.supplier_id = receipt_in.supplier_id
    receipt.location_id = stock.resolve_location(
        session, receipt_in.location_id
    )
    _apply(session, receipt, receipt_in)
    session.commit()
    return receipt


def discard_draft(
    session: Session, receipt: GoodsReceipt, *, actor: User
) -> None:
    _require_draft(receipt)
    activity_log.record(
        session,
        actor=actor,
        action='goods_receipt.discard',
        summary='Membuang draf barang masuk.',
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    session.delete(receipt)
    session.commit()


def complete(
    session: Session, receipt: GoodsReceipt, *, actor: User
) -> GoodsReceipt:
    """Write the receipt's Stock Movements; from here on it is immutable."""
    # Lock the receipt, so two people completing it can't both get through.
    assert receipt.id is not None
    receipt = documents.lock(session, GoodsReceipt, receipt.id)
    _require_draft(receipt)
    assert receipt.id is not None
    if not receipt.lines:
        raise ConflictError('Barang masuk belum punya isi.')
    supplier = _usable_supplier(session, receipt.supplier_id)

    receipt.number = documents.next_number(session, PREFIX)
    receipt.status = DocumentStatus.completed
    receipt.completed_by = actor.id
    receipt.completed_at = utc_now()
    session.add(receipt)

    source = costing.Source(DOCUMENT_TYPE, receipt.id, receipt.number)
    # Always in SKU order, so two receipts can't lock each other out.
    for line in sorted(receipt.lines, key=lambda line: line.sku_id):
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        costing.receive(
            session,
            sku=sku,
            location_id=receipt.location_id,
            quantity=line.quantity,
            value=line.total_cost,
            reason=MovementReason.goods_receipt,
            source=source,
            actor=actor,
        )
    activity_log.record(
        session,
        actor=actor,
        action='goods_receipt.complete',
        summary=(
            f'Menyelesaikan barang masuk {receipt.number} dari '
            f'{supplier.name}: {len(receipt.lines)} baris, '
            f'{rupiah(round(receipt.total_cost))}.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    posting.goods_receipt(session, receipt, actor=actor)
    session.commit()
    return receipt


def reverse(
    session: Session, receipt: GoodsReceipt, reason: str, *, actor: User
) -> GoodsReceipt:
    assert receipt.id is not None
    receipt = documents.lock(session, GoodsReceipt, receipt.id)
    returns = session.exec(
        select(SupplierReturn.number).where(
            SupplierReturn.goods_receipt_id == receipt.id,
            SupplierReturn.status == DocumentStatus.completed,
        )
    ).all()
    if returns:
        raise ConflictError(
            f'Barang masuk {receipt.number} sudah diretur ({", ".join(n for n in returns if n)}). '
            'Batalkan returnya dulu.'
        )
    documents.reverse(
        session,
        receipt,
        document_type=DOCUMENT_TYPE,
        label=f'barang masuk {receipt.number}',
        reason=reason,
        actor=actor,
    )
    session.commit()
    return receipt


def returned_quantities(
    session: Session, receipt: GoodsReceipt
) -> dict[int, Decimal]:
    """Per receipt line: how much went back on completed Supplier Returns."""
    rows = session.exec(
        select(
            SupplierReturnLine.goods_receipt_line_id,
            func.sum(SupplierReturnLine.quantity),
        )
        .join(SupplierReturn)
        .where(
            SupplierReturn.goods_receipt_id == receipt.id,
            SupplierReturn.status == DocumentStatus.completed,
        )
        .group_by(col(SupplierReturnLine.goods_receipt_line_id))
    ).all()
    return {line_id: total for line_id, total in rows}


def _apply(
    session: Session, receipt: GoodsReceipt, receipt_in: GoodsReceiptSave
) -> None:
    """Set the draft's header and replace its lines with those sent."""
    receipt.received_on = receipt_in.received_on
    receipt.supplier_invoice = (
        receipt_in.supplier_invoice or ''
    ).strip() or None
    receipt.payment_status = receipt_in.payment_status
    receipt.paid_from_account_id = (
        ledger.paying_account(session, receipt_in.paid_from_account_id)
        if receipt_in.payment_status == PaymentStatus.paid
        else None
    )
    receipt.note = (receipt_in.note or '').strip() or None
    for line in list(receipt.lines):
        session.delete(line)
    session.add(receipt)
    session.flush()
    assert receipt.id is not None

    total = Decimal(0)
    for row in receipt_in.lines:
        sku = session.get(Sku, row.sku_id)
        if sku is None:
            raise NotFoundError('SKU tidak ditemukan.')
        line = GoodsReceiptLine(
            receipt_id=receipt.id,
            sku_id=row.sku_id,
            quantity=row.quantity,
            unit_cost=row.unit_cost,
            total_cost=costing.money(row.quantity * row.unit_cost),
        )
        if row.in_packs:
            if sku.purchase_pack_size is None:
                label = sku_label(sku.product.name, sku.size, sku.color)
                raise AppError(f'{label} tidak punya kemasan beli.')
            line.pack_name = sku.purchase_pack_name
            line.pack_size = sku.purchase_pack_size
            line.pack_quantity = row.quantity
            line.pack_cost = row.unit_cost
            line.quantity = row.quantity * sku.purchase_pack_size
            line.unit_cost = costing.money(
                row.unit_cost / sku.purchase_pack_size
            )
        total += line.total_cost
        session.add(line)
    receipt.total_cost = total
    session.flush()
    session.refresh(receipt)


def _require_draft(receipt: GoodsReceipt) -> None:
    if receipt.status != DocumentStatus.draft:
        raise ConflictError(
            f'Barang masuk {receipt.number} sudah diselesaikan '
            'dan tidak bisa diubah.'
        )


def _usable_supplier(session: Session, supplier_id: int) -> Supplier:
    supplier = suppliers.get_supplier(session, supplier_id)
    if not supplier.is_active:
        raise ConflictError(f'Pemasok {supplier.name} sudah nonaktif.')
    return supplier
