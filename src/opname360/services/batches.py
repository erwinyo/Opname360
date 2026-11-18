"""Medicine Batches (slice 6): which Batch each unit of a SKU is in.

Stock value and costing stay per SKU; a Batch only splits the quantity.
Rules are in docs/plan/slice-6-later.md.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError
from opname360.core.formatting import sku_label
from opname360.models import (
    Batch,
    BatchStock,
    MovementReason,
    Sku,
    StockMovement,
)
from opname360.services.documents import shop_now


def tracks(sku: Sku) -> bool:
    return sku.product.sub_category.category.tracks_batches


def today() -> date:
    return shop_now().date()


def is_expired_on(expires_on: date, on: date) -> bool:
    """Expired once the day after its expiry date begins (rule 9)."""
    return expires_on < on


def is_expired(batch: Batch, on: date) -> bool:
    return is_expired_on(batch.expires_on, on)


def clean_number(number: str | None) -> str | None:
    return (number or '').strip().upper() or None


def long_date(day: date) -> str:
    return f'{day:%d-%m-%Y}'


def resolve(
    session: Session, sku: Sku, number: str, expires_on: date
) -> Batch:
    """The SKU's Batch with this number, created if new (rule 6)."""
    assert sku.id is not None
    session.exec(
        insert(Batch)
        .values(sku_id=sku.id, number=number, expires_on=expires_on)
        .on_conflict_do_nothing()
    )
    batch = session.exec(
        select(Batch).where(Batch.sku_id == sku.id, Batch.number == number)
    ).one()
    if batch.expires_on != expires_on:
        label = sku_label(sku.product.name, sku.size, sku.color)
        raise ConflictError(
            f'{label}: batch {number} sudah tercatat kedaluwarsa '
            f'{long_date(batch.expires_on)}, bukan {long_date(expires_on)}.'
        )
    return batch


def find(session: Session, sku_id: int, number: str | None) -> Batch | None:
    if number is None:
        return None
    return session.exec(
        select(Batch).where(Batch.sku_id == sku_id, Batch.number == number)
    ).first()


def quantities(
    session: Session, sku_id: int, location_id: int
) -> list[tuple[Batch, Decimal]]:
    """Every Batch of the SKU with its quantity at the Location, the one
    that expires first first."""
    rows = session.exec(
        select(Batch, func.coalesce(func.sum(StockMovement.quantity), 0))
        .join(
            StockMovement,
            and_(
                col(StockMovement.batch_id) == Batch.id,
                col(StockMovement.location_id) == location_id,
            ),
            isouter=True,
        )
        .where(Batch.sku_id == sku_id)
        .group_by(col(Batch.id))
        .order_by(col(Batch.expires_on), col(Batch.id))
    ).all()
    return [(batch, Decimal(quantity)) for batch, quantity in rows]


def stock(session: Session, sku_id: int, location_id: int) -> list[BatchStock]:
    on = today()
    return [
        BatchStock.model_validate(
            batch,
            update={'quantity': quantity, 'expired': is_expired(batch, on)},
        )
        for batch, quantity in quantities(session, sku_id, location_id)
    ]


def allocate(
    session: Session, sku: Sku, location_id: int, quantity: Decimal
) -> list[tuple[int, Decimal]]:
    """Which Batches a sale of `quantity` takes from (rules 9-11).

    The one that expires first goes first; what no unexpired Batch holds
    goes out of that first one too. Raises when the till must refuse
    (rule 10). To be exact, the caller holds the SKU's balance lock.
    """
    assert sku.id is not None
    on = today()
    label = sku_label(sku.product.name, sku.size, sku.color)
    rows = quantities(session, sku.id, location_id)
    fresh = [
        (batch, held) for batch, held in rows if not is_expired(batch, on)
    ]
    stale = [
        batch for batch, held in rows if is_expired(batch, on) and held > 0
    ]
    if not rows:
        raise ConflictError(
            f'{label} belum punya batch tercatat, jadi tanggal '
            'kedaluwarsanya tidak diketahui. Catat lewat Barang Masuk atau '
            'Stok Opname dulu.'
        )
    if not fresh:
        latest = rows[-1][0]
        raise ConflictError(
            f'{label}: semua batch sudah kedaluwarsa (terakhir batch '
            f'{latest.number}, {long_date(latest.expires_on)}). Jangan '
            'dijual; serahkan ke Admin.'
        )
    unexpired = sum((max(held, Decimal(0)) for _, held in fresh), Decimal(0))
    if quantity > unexpired and stale:
        numbers = ', '.join(batch.number for batch in stale)
        raise ConflictError(
            f'{label}: yang belum kedaluwarsa tinggal '
            f'{unexpired.normalize():f} {sku.stock_unit}; sisanya batch '
            f'{numbers} yang sudah kedaluwarsa. Jangan dijual; serahkan ke '
            'Admin.'
        )
    takes: dict[int, Decimal] = {}
    left = quantity
    for batch, held in fresh:
        take = min(left, max(held, Decimal(0)))
        if take > 0:
            assert batch.id is not None
            takes[batch.id] = take
            left -= take
    if left > 0:
        first = fresh[0][0].id
        assert first is not None
        takes[first] = takes.get(first, Decimal(0)) + left
    return list(takes.items())


def sold_from(session: Session, receipt_id: int, sku_id: int) -> int | None:
    """The Batch a Receipt sold this SKU from; of several, the one that
    expires first (rule 12)."""
    return session.exec(
        select(Batch.id)
        .join(StockMovement, col(StockMovement.batch_id) == Batch.id)
        .where(
            StockMovement.document_type == 'receipt',
            StockMovement.document_id == receipt_id,
            StockMovement.sku_id == sku_id,
            StockMovement.reason == MovementReason.sale,
        )
        .order_by(col(Batch.expires_on), col(Batch.id))
        .limit(1)
    ).first()
