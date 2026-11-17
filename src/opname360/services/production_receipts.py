from decimal import Decimal

from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError, NotFoundError
from opname360.core.formatting import rupiah
from opname360.models import (
    DocumentStatus,
    Location,
    MovementReason,
    ProductionReceipt,
    ProductionReceiptFilter,
    ProductionReceiptLine,
    ProductionReceiptLinePublic,
    ProductionReceiptPage,
    ProductionReceiptPublic,
    ProductionReceiptSave,
    ProductionReceiptSummary,
    Sku,
    User,
)
from opname360.models._types import utc_now
from opname360.services import (
    activity_log,
    costing,
    documents,
    posting,
    stock,
)


PREFIX = 'HP'  # Hasil Produksi
DOCUMENT_TYPE = 'production_receipt'


def list_receipts(
    session: Session, filters: ProductionReceiptFilter
) -> ProductionReceiptPage:
    query = select(ProductionReceipt)
    if filters.status is not None:
        query = query.where(ProductionReceipt.status == filters.status)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    receipts = session.exec(
        query.order_by(col(ProductionReceipt.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    line_counts = dict(
        session.exec(
            select(ProductionReceiptLine.receipt_id, func.count())
            .where(
                col(ProductionReceiptLine.receipt_id).in_(
                    [receipt.id for receipt in receipts]
                )
            )
            .group_by(col(ProductionReceiptLine.receipt_id))
        ).all()
    )
    return ProductionReceiptPage(
        items=[
            ProductionReceiptSummary.model_validate(
                receipt,
                update={'line_count': line_counts.get(receipt.id, 0)},
            )
            for receipt in receipts
        ],
        total=total,
    )


def get_receipt(session: Session, receipt_id: int) -> ProductionReceipt:
    receipt = session.get(ProductionReceipt, receipt_id)
    if receipt is None:
        raise NotFoundError('Hasil produksi tidak ditemukan.')
    return receipt


def receipt_public(
    session: Session, receipt: ProductionReceipt
) -> ProductionReceiptPublic:
    location = session.get(Location, receipt.location_id)
    assert location is not None
    lines = []
    for line in receipt.lines:
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        lines.append(
            ProductionReceiptLinePublic.model_validate(
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
    return ProductionReceiptPublic.model_validate(
        receipt,
        update={
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
            'lines': lines,
        },
    )


def create_draft(
    session: Session, receipt_in: ProductionReceiptSave, *, actor: User
) -> ProductionReceipt:
    receipt = ProductionReceipt(
        location_id=stock.resolve_location(session, receipt_in.location_id),
        produced_on=receipt_in.produced_on,
        created_by=actor.id,
    )
    _apply(session, receipt, receipt_in)
    activity_log.record(
        session,
        actor=actor,
        action='production_receipt.create',
        summary='Membuat draf hasil produksi.',
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    session.commit()
    return receipt


def update_draft(
    session: Session,
    receipt: ProductionReceipt,
    receipt_in: ProductionReceiptSave,
    *,
    actor: User,
) -> ProductionReceipt:
    _require_draft(receipt)
    receipt.location_id = stock.resolve_location(
        session, receipt_in.location_id
    )
    _apply(session, receipt, receipt_in)
    session.commit()
    return receipt


def discard_draft(
    session: Session, receipt: ProductionReceipt, *, actor: User
) -> None:
    _require_draft(receipt)
    activity_log.record(
        session,
        actor=actor,
        action='production_receipt.discard',
        summary='Membuang draf hasil produksi.',
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    session.delete(receipt)
    session.commit()


def complete(
    session: Session, receipt: ProductionReceipt, *, actor: User
) -> ProductionReceipt:
    assert receipt.id is not None
    receipt = documents.lock(session, ProductionReceipt, receipt.id)
    _require_draft(receipt)
    assert receipt.id is not None
    if not receipt.lines:
        raise ConflictError('Hasil produksi belum punya isi.')

    receipt.number = documents.next_number(session, PREFIX)
    receipt.status = DocumentStatus.completed
    receipt.completed_by = actor.id
    receipt.completed_at = utc_now()
    session.add(receipt)

    source = costing.Source(DOCUMENT_TYPE, receipt.id, receipt.number)
    for line in sorted(receipt.lines, key=lambda line: line.sku_id):
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        costing.receive(
            session,
            sku=sku,
            location_id=receipt.location_id,
            quantity=line.quantity,
            value=line.total_cost,
            reason=MovementReason.production_receipt,
            source=source,
            actor=actor,
        )
    activity_log.record(
        session,
        actor=actor,
        action='production_receipt.complete',
        summary=(
            f'Menyelesaikan hasil produksi {receipt.number}: '
            f'{len(receipt.lines)} baris, '
            f'{rupiah(round(receipt.total_cost))}.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    posting.production_receipt(session, receipt, actor=actor)
    session.commit()
    return receipt


def reverse(
    session: Session, receipt: ProductionReceipt, reason: str, *, actor: User
) -> ProductionReceipt:
    assert receipt.id is not None
    receipt = documents.lock(session, ProductionReceipt, receipt.id)
    documents.reverse(
        session,
        receipt,
        document_type=DOCUMENT_TYPE,
        label=f'hasil produksi {receipt.number}',
        reason=reason,
        actor=actor,
    )
    session.commit()
    return receipt


def _apply(
    session: Session,
    receipt: ProductionReceipt,
    receipt_in: ProductionReceiptSave,
) -> None:
    receipt.produced_on = receipt_in.produced_on
    receipt.note = (receipt_in.note or '').strip() or None
    for line in list(receipt.lines):
        session.delete(line)
    session.add(receipt)
    session.flush()
    assert receipt.id is not None

    total = Decimal(0)
    for row in receipt_in.lines:
        if session.get(Sku, row.sku_id) is None:
            raise NotFoundError('SKU tidak ditemukan.')
        line = ProductionReceiptLine(
            receipt_id=receipt.id,
            sku_id=row.sku_id,
            quantity=row.quantity,
            unit_cost=row.unit_cost,
            total_cost=costing.money(row.quantity * row.unit_cost),
        )
        total += line.total_cost
        session.add(line)
    receipt.total_cost = total
    session.flush()
    session.refresh(receipt)


def _require_draft(receipt: ProductionReceipt) -> None:
    if receipt.status != DocumentStatus.draft:
        raise ConflictError(
            f'Hasil produksi {receipt.number} sudah diselesaikan '
            'dan tidak bisa diubah.'
        )
