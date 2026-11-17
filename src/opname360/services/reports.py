"""Reports (slice 4). They add no records: every figure is worked out from
Stock Movements, Receipts and Stock Opnames. Days and hours are the shop's
(rule 7)."""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import groupby
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import distinct_on
from sqlmodel import Session, case, col, func, select

from opname360.core.config import settings
from opname360.models import (
    Category,
    DailyStock,
    DailyStockCategory,
    DailyStockFilter,
    DailyStockRow,
    DailyStockSubCategory,
    Location,
    Product,
    Sku,
    StockFlow,
    StockMovement,
    SubCategory,
)
from opname360.services import stock


ZERO = Decimal(0)
FLOW = ('opening', 'quantity_in', 'quantity_out', 'closing', 'closing_value')


def shop_zone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def day_start(day: date) -> datetime:
    """00:00 of a Shop Day, as an aware datetime."""
    return datetime.combine(day, time(), tzinfo=shop_zone())


def day_bounds(
    first: date, last: date | None = None
) -> tuple[datetime, datetime]:
    """From the start of `first` to the end of `last` (the same day if not
    given): start included, end excluded."""
    return day_start(first), day_start((last or first) + timedelta(days=1))


# Laporan Stok Harian


def daily_stock(session: Session, filters: DailyStockFilter) -> DailyStock:
    """Per SKU: opening, in, out, closing and closing value (rules 5, 6).

    One day's closing is the next day's opening because both are the
    balance after the last Stock Movement before a midnight.
    """
    location_id = stock.resolve_location(session, filters.location_id)
    location = session.get(Location, location_id)
    assert location is not None
    start, end = day_bounds(filters.day)
    opening = _balances_before(session, location_id, start)
    closing = _balances_before(session, location_id, end)
    moved = {
        sku_id: (quantity_in, quantity_out)
        for sku_id, quantity_in, quantity_out in session.exec(
            select(
                StockMovement.sku_id,
                func.sum(
                    case(
                        (
                            col(StockMovement.quantity) > 0,
                            StockMovement.quantity,
                        ),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (
                            col(StockMovement.quantity) < 0,
                            -col(StockMovement.quantity),
                        ),
                        else_=0,
                    )
                ),
            )
            .where(
                StockMovement.location_id == location_id,
                col(StockMovement.created_at) >= start,
                col(StockMovement.created_at) < end,
            )
            .group_by(col(StockMovement.sku_id))
        ).all()
    }

    conditions = []
    if filters.category_id is not None:
        conditions.append(SubCategory.category_id == filters.category_id)
    if filters.sub_category_id is not None:
        conditions.append(Product.sub_category_id == filters.sub_category_id)
    skus = session.exec(
        select(Sku, Product, SubCategory, Category)
        .join(Product, col(Sku.product_id) == Product.id)
        .join(SubCategory, col(Product.sub_category_id) == SubCategory.id)
        .join(Category, col(SubCategory.category_id) == Category.id)
        .where(*conditions)
        .order_by(
            col(Category.name),
            col(Category.id),
            col(SubCategory.name),
            col(SubCategory.id),
            col(Product.name),
            col(Sku.id),
        )
    ).all()

    categories = []
    in_scope = [row for row in skus if row[0].id in closing]
    for category, by_category in groupby(in_scope, key=lambda row: row[3]):
        sub_categories = []
        for sub_category, by_sub in groupby(by_category, key=lambda r: r[2]):
            rows = []
            for sku, product, _, _ in by_sub:
                assert sku.id is not None
                opened = opening.get(sku.id, (ZERO, ZERO))[0]
                closed, value = closing[sku.id]
                quantity_in, quantity_out = moved.get(sku.id, (ZERO, ZERO))
                rows.append(
                    DailyStockRow(
                        sku_id=sku.id,
                        product_name=product.name,
                        size=sku.size,
                        color=sku.color,
                        code=sku.code,
                        stock_unit=sku.stock_unit,
                        opening=opened,
                        quantity_in=quantity_in,
                        quantity_out=quantity_out,
                        closing=closed,
                        closing_value=value,
                    )
                )
            sub_categories.append(
                DailyStockSubCategory(
                    id=sub_category.id or 0,
                    name=sub_category.name,
                    rows=rows,
                    **_total(rows),
                )
            )
        categories.append(
            DailyStockCategory(
                id=category.id or 0,
                name=category.name,
                sub_categories=sub_categories,
                **_total(sub_categories),
            )
        )
    return DailyStock(
        day=filters.day,
        location_name=location.name,
        categories=categories,
        **_total(categories),
    )


def _balances_before(
    session: Session, location_id: int, before: datetime
) -> dict[int, tuple[Decimal, Decimal]]:
    """Each SKU's quantity and Stock Value after its last Stock Movement
    before `before`. SKUs that never moved are left out."""
    # ponytail: scans all history up to `before`; a daily balance snapshot
    # if this ever gets slow.
    rows = session.exec(
        select(
            col(StockMovement.sku_id),
            col(StockMovement.quantity_after),
            col(StockMovement.value_after),
        )
        .ext(distinct_on(col(StockMovement.sku_id)))
        .where(
            StockMovement.location_id == location_id,
            col(StockMovement.created_at) < before,
        )
        .order_by(col(StockMovement.sku_id), col(StockMovement.id).desc())
    ).all()
    return {sku_id: (quantity, value) for sku_id, quantity, value in rows}


def _total(parts: Sequence[StockFlow]) -> dict[str, Decimal]:
    return {
        name: sum((getattr(part, name) for part in parts), ZERO)
        for name in FLOW
    }
