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
from opname360.models import Batch, BatchStock, Sku, StockMovement
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
