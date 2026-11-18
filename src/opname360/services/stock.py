from decimal import Decimal
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from opname360.core.errors import NotFoundError
from opname360.models import (
    Batch,
    Location,
    LocationPublic,
    Product,
    Sku,
    StockBalance,
    StockCard,
    StockCardEntry,
    StockFilter,
    StockMovement,
    StockPage,
    StockRow,
    SubCategory,
    User,
)
from opname360.services import batches


def list_locations(session: Session) -> list[Location]:
    return list(
        session.exec(select(Location).order_by(col(Location.id))).all()
    )


def resolve_location(session: Session, location_id: int | None) -> int:
    """The given Location's id, or the shop's first one when none is given."""
    if location_id is None:
        location = session.exec(
            select(Location).order_by(col(Location.id)).limit(1)
        ).one()
    else:
        location = session.get(Location, location_id)
        if location is None:
            raise NotFoundError('Lokasi tidak ditemukan.')
    assert location.id is not None
    return location.id


def has_movements(session: Session, sku_ids: list[int]) -> bool:
    if not sku_ids:
        return False
    found = session.exec(
        select(StockMovement.id)
        .where(col(StockMovement.sku_id).in_(sku_ids))
        .limit(1)
    ).first()
    return found is not None


def list_stock(session: Session, filters: StockFilter) -> StockPage:
    location_id = resolve_location(session, filters.location_id)

    conditions = []
    if filters.sub_category_id is not None:
        conditions.append(Product.sub_category_id == filters.sub_category_id)
    if filters.category_id is not None:
        conditions.append(SubCategory.category_id == filters.category_id)
    if filters.negative_only:
        conditions.append(col(StockBalance.quantity) < 0)
    search = (filters.search or '').strip()
    if search:
        conditions.append(
            or_(
                col(Product.name).icontains(search, autoescape=True),
                col(Sku.code).icontains(search, autoescape=True),
                col(Sku.barcode).icontains(search, autoescape=True),
            )
        )

    def scoped(query: Any) -> Any:
        """Every SKU in the filter, with its balance here if it has one."""
        return (
            query.select_from(Sku)
            .join(Product, col(Sku.product_id) == Product.id)
            .join(SubCategory, col(Product.sub_category_id) == SubCategory.id)
            .join(
                StockBalance,
                and_(
                    col(StockBalance.sku_id) == Sku.id,
                    col(StockBalance.location_id) == location_id,
                ),
                isouter=True,
            )
            .where(*conditions)
        )

    total, total_value = session.exec(
        scoped(
            select(
                func.count(col(Sku.id)),
                func.coalesce(func.sum(StockBalance.value), 0),
            )
        )
    ).one()
    rows = session.exec(
        scoped(select(Sku, StockBalance))
        .options(
            selectinload(Sku.product)  # ty: ignore[invalid-argument-type]
            .selectinload(Product.sub_category)  # ty: ignore[invalid-argument-type]
            .selectinload(SubCategory.category)  # ty: ignore[invalid-argument-type]
        )
        .order_by(col(Product.name), col(Sku.id))
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return StockPage(
        items=[_stock_row(sku, balance) for sku, balance in rows],
        total=total,
        total_value=total_value,
    )


def stock_card(
    session: Session,
    sku: Sku,
    *,
    location_id: int | None,
    offset: int,
    limit: int,
) -> StockCard:
    location = session.get(Location, resolve_location(session, location_id))
    assert location is not None
    balance = session.get(StockBalance, (sku.id, location.id))
    scope = (
        StockMovement.sku_id == sku.id,
        StockMovement.location_id == location.id,
    )
    total = session.exec(
        select(func.count()).select_from(StockMovement).where(*scope)
    ).one()
    rows = session.exec(
        select(StockMovement, User.full_name, Batch.number)
        .join(User, isouter=True)
        .join(Batch, isouter=True)
        .where(*scope)
        .order_by(col(StockMovement.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    assert sku.id is not None and location.id is not None
    return StockCard(
        sku=_stock_row(sku, balance),
        location=LocationPublic.model_validate(location),
        batches=batches.stock(session, sku.id, location.id),
        items=[
            StockCardEntry.model_validate(
                movement,
                update={'created_by_name': name, 'batch_number': number},
            )
            for movement, name, number in rows
        ],
        total=total,
    )


def _stock_row(sku: Sku, balance: StockBalance | None) -> StockRow:
    product = sku.product
    sub_category = product.sub_category
    assert sku.id is not None
    assert product.id is not None
    return StockRow(
        sku_id=sku.id,
        product_id=product.id,
        product_name=product.name,
        size=sku.size,
        color=sku.color,
        code=sku.code,
        barcode=sku.barcode,
        stock_unit=sku.stock_unit,
        is_active=sku.is_active,
        category_name=sub_category.category.name,
        sub_category_name=sub_category.name,
        quantity=balance.quantity if balance else Decimal(0),
        value=balance.value if balance else Decimal(0),
    )
