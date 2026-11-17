"""Reports (slice 4). They add no records: every figure is worked out from
Stock Movements, Receipts and Stock Opnames. Days and hours are the shop's
(rule 7)."""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import groupby
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Date, and_, cast, not_
from sqlalchemy.dialects.postgresql import distinct_on
from sqlmodel import Session, case, col, func, or_, select

from opname360.core.config import settings
from opname360.models import (
    AbcClass,
    AbcClassTotal,
    AbcReport,
    AbcRow,
    ActivityLog,
    Category,
    DailyStock,
    DailyStockCategory,
    DailyStockFilter,
    DailyStockRow,
    DailyStockSubCategory,
    Dashboard,
    FastMoving,
    FastMovingFilter,
    FastMovingRow,
    HourFigures,
    HourlySales,
    Location,
    Payment,
    PaymentMethod,
    Product,
    ProductSalesFilter,
    Receipt,
    ReceiptLine,
    ReceiptStatus,
    SalesFigures,
    SalesFilter,
    SalesGroupBy,
    SalesReceipt,
    SalesReceiptFilter,
    SalesReceiptPage,
    SalesReport,
    SalesRow,
    Sku,
    StockBalance,
    StockFlow,
    StockMovement,
    SubCategory,
    User,
)
from opname360.services import shop_settings, stock
from opname360.services.documents import shop_now


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


# Penjualan, Laba Kotor per Jam and the Dasbor

RECEIPT = 'receipt'
# What a sales figure is grouped by; None is the whole period.
type By = Literal['hour', 'day', 'category', 'cashier'] | None


def _local(column: Any) -> Any:
    """A timestamp as the shop's wall-clock time."""
    return func.timezone(settings.timezone, column)


def _empty() -> SalesFigures:
    return SalesFigures(
        receipt_count=0,
        gross_sales=0,
        discounts=0,
        refunds=0,
        net_sales=0,
        cogs=ZERO,
        gross_profit=ZERO,
    )


def _by_category(query: Any, sku_id: Any) -> Any:
    return (
        query.join(Sku, sku_id == Sku.id)
        .join(Product, col(Sku.product_id) == Product.id)
        .join(SubCategory, col(Product.sub_category_id) == SubCategory.id)
    )


def _sales(
    session: Session, start: datetime, end: datetime, by: By
) -> dict[Any, SalesFigures]:
    """Net Sales and COGS of completed Receipts, by the time each Receipt
    was made (rules 1-3), plus Negative Stock cost adjustments by the time
    they were booked."""
    created = col(Receipt.created_at)
    line_key = {
        None: None,
        'hour': func.extract('hour', _local(created)),
        'day': cast(_local(created), Date),
        'category': col(SubCategory.category_id),
        'cashier': col(Receipt.cashier_id),
    }[by]
    sold = col(ReceiptLine.quantity) > 0
    total = col(ReceiptLine.line_total)
    columns: list[Any] = [
        *([] if line_key is None else [line_key]),
        func.count(func.distinct(Receipt.id)),
        func.sum(case((sold, total + col(ReceiptLine.discount)), else_=0)),
        func.sum(case((sold, ReceiptLine.discount), else_=0)),
        func.sum(case((sold, 0), else_=-total)),
        func.sum(total),
        # Each line's cost to 4 decimals, so hours add up to the day.
        func.sum(
            func.round(
                col(ReceiptLine.quantity) * col(ReceiptLine.unit_cogs), 4
            )
        ),
    ]
    query: Any = (
        select(*columns)
        .select_from(ReceiptLine)
        .join(Receipt, col(ReceiptLine.receipt_id) == Receipt.id)
        .where(
            Receipt.status == ReceiptStatus.completed,
            created >= start,
            created < end,
        )
    )
    if by == 'category':
        query = _by_category(query, col(ReceiptLine.sku_id))
    if line_key is not None:
        query = query.group_by(line_key)

    figures: dict[Any, SalesFigures] = {}
    for row in session.exec(query).all():
        key, values = (None, row) if line_key is None else (row[0], row[1:])
        count, gross, discounts, refunds, net, cogs = values
        if count == 0:
            continue
        figures[_key(key)] = SalesFigures(
            receipt_count=count,
            gross_sales=gross,
            discounts=discounts,
            refunds=refunds,
            net_sales=net,
            cogs=cogs,
            gross_profit=net - cogs,
        )
    if by == 'cashier':
        # COGS belongs to goods; a Cashier's figures stop at Net Sales.
        return {
            key: value.model_copy(update={'cogs': None, 'gross_profit': None})
            for key, value in figures.items()
        }

    for key, adjustment in _cost_adjustments(session, start, end, by).items():
        current = figures.get(key) or _empty()
        cogs = (current.cogs or ZERO) + adjustment
        figures[key] = current.model_copy(
            update={'cogs': cogs, 'gross_profit': current.net_sales - cogs}
        )
    return figures


def _cost_adjustments(
    session: Session, start: datetime, end: datetime, by: By
) -> dict[Any, Decimal]:
    """Stock Value moved without goods moving (costing rule 6, and the
    Reversals of such moves) is COGS on the day it is booked. A voided
    Receipt's count for nothing."""
    created = col(StockMovement.created_at)
    key = {
        None: None,
        'hour': func.extract('hour', _local(created)),
        'day': cast(_local(created), Date),
        'category': col(SubCategory.category_id),
    }[by]
    voided = select(Receipt.id).where(Receipt.status == ReceiptStatus.voided)
    query: Any = select(
        *([] if key is None else [key]),
        func.sum(-col(StockMovement.value)),
    ).where(
        StockMovement.quantity == 0,
        created >= start,
        created < end,
        not_(
            and_(
                col(StockMovement.document_type) == RECEIPT,
                col(StockMovement.document_id).in_(voided),
            )
        ),
    )
    if by == 'category':
        query = _by_category(query, col(StockMovement.sku_id))
    if key is not None:
        query = query.group_by(key)
    rows = session.exec(query).all()
    if key is None:
        [amount] = rows
        return {} if amount is None else {None: amount}
    return {_key(key): amount for key, amount in rows}


def _key(value: Any) -> Any:
    """Hours come back from PostgreSQL as numbers like 9.000000."""
    return int(value) if isinstance(value, Decimal) else value


def hourly_sales(session: Session, day: date) -> HourlySales:
    start, end = day_bounds(day)
    by_hour = _sales(session, start, end, 'hour')
    hours = [
        HourFigures(hour=hour, **by_hour.get(hour, _empty()).model_dump())
        for hour in range(24)
    ]
    total = _sales(session, start, end, None).get(None, _empty())
    return HourlySales(day=day, hours=hours, **total.model_dump())


def sales_report(session: Session, filters: SalesFilter) -> SalesReport:
    start, end = day_bounds(filters.start, filters.end)
    total = _sales(session, start, end, None).get(None, _empty())
    group_by = filters.group_by
    rows: list[SalesRow]
    if group_by == SalesGroupBy.day:
        by_day = _sales(session, start, end, 'day')
        days = (
            filters.start + timedelta(days=offset)
            for offset in range((filters.end - filters.start).days + 1)
        )
        rows = [
            SalesRow(
                key=day.isoformat(),
                label=day.isoformat(),
                **by_day.get(day, _empty()).model_dump(),
            )
            for day in days
        ]
    elif group_by == SalesGroupBy.payment_method:
        rows = _by_payment_method(session, start, end)
    else:
        by = 'category' if group_by == SalesGroupBy.category else 'cashier'
        model = Category if by == 'category' else User
        figures = _sales(session, start, end, by)
        names = {
            item.id: getattr(item, 'name', None)
            or getattr(item, 'full_name', '')
            for item in session.exec(
                select(model).where(col(model.id).in_(figures))
            ).all()
        }
        rows = sorted(
            (
                SalesRow(key=str(key), label=names[key], **value.model_dump())
                for key, value in figures.items()
            ),
            key=lambda row: (-row.net_sales, row.label),
        )
    return SalesReport(
        start=filters.start,
        end=filters.end,
        group_by=group_by,
        rows=rows,
        total=total,
    )


def _by_payment_method(
    session: Session, start: datetime, end: datetime
) -> list[SalesRow]:
    """What each Payment Method took, net of change and money paid back."""
    rows = session.exec(
        select(
            PaymentMethod.id,
            PaymentMethod.name,
            func.count(func.distinct(Receipt.id)),
            func.sum(Payment.amount),
        )
        .select_from(Payment)
        .join(Receipt, col(Payment.receipt_id) == Receipt.id)
        .join(
            PaymentMethod, col(Payment.payment_method_id) == PaymentMethod.id
        )
        .where(
            Receipt.status == ReceiptStatus.completed,
            col(Receipt.created_at) >= start,
            col(Receipt.created_at) < end,
        )
        .group_by(col(PaymentMethod.id), col(PaymentMethod.name))
        .order_by(func.sum(Payment.amount).desc(), col(PaymentMethod.name))
    ).all()
    return [
        SalesRow(
            key=str(method_id),
            label=name,
            receipt_count=count,
            gross_sales=None,
            discounts=None,
            refunds=None,
            net_sales=amount,
            cogs=None,
            gross_profit=None,
        )
        for method_id, name, count, amount in rows
    ]


def sales_receipts(
    session: Session, filters: SalesReceiptFilter
) -> SalesReceiptPage:
    """The completed Receipts behind one row of Penjualan, newest first."""
    start, end = day_bounds(filters.start, filters.end)
    amount: Any
    if filters.category_id is not None:
        amount = _by_category(
            select(
                col(ReceiptLine.receipt_id).label('id'),
                func.sum(ReceiptLine.line_total).label('amount'),
            ),
            col(ReceiptLine.sku_id),
        ).where(SubCategory.category_id == filters.category_id)
        amount = amount.group_by(col(ReceiptLine.receipt_id))
    elif filters.payment_method_id is not None:
        amount = (
            select(
                col(Payment.receipt_id).label('id'),
                func.sum(Payment.amount).label('amount'),
            )
            .where(Payment.payment_method_id == filters.payment_method_id)
            .group_by(col(Payment.receipt_id))
        )
    else:
        amount = select(
            col(Receipt.id).label('id'), col(Receipt.total).label('amount')
        )
    amounts = amount.subquery()
    conditions = [
        Receipt.status == ReceiptStatus.completed,
        col(Receipt.created_at) >= start,
        col(Receipt.created_at) < end,
    ]
    if filters.cashier_id is not None:
        conditions.append(Receipt.cashier_id == filters.cashier_id)

    def scoped(query: Any) -> Any:
        return (
            query.select_from(Receipt)
            .join(amounts, amounts.c.id == Receipt.id)
            .join(User, col(Receipt.cashier_id) == User.id)
            .where(*conditions)
        )

    total = session.exec(scoped(select(func.count()))).one()
    rows = session.exec(
        scoped(select(Receipt, User.full_name, amounts.c.amount))
        .order_by(col(Receipt.created_at).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return SalesReceiptPage(
        items=[
            SalesReceipt(
                id=receipt.id or 0,
                number=receipt.number,
                kind=receipt.kind,
                created_at=receipt.created_at,
                cashier_name=name,
                amount=value,
            )
            for receipt, name, value in rows
        ],
        total=total,
    )


def shown_hours(session: Session, report: HourlySales) -> list[int]:
    """The shop's opening hours, and any other hour something happened."""
    shop = shop_settings.get_settings(session)
    closes = shop.closes_at.hour + (1 if shop.closes_at.minute else 0)
    return [
        figures.hour
        for figures in report.hours
        if shop.opens_at.hour <= figures.hour < closes
        or figures.receipt_count
        or figures.cogs
    ]


def dashboard(session: Session) -> Dashboard:
    return Dashboard(today=hourly_sales(session, shop_now().date()))


def latest_activity(session: Session) -> int:
    """Grows with everything recorded: the live dashboard's signal."""
    return session.exec(select(func.max(ActivityLog.id))).one() or 0


# Fast Moving and Kontribusi Omzet

A_LINE = Decimal('0.80')
B_LINE = Decimal('0.95')
SHARE = Decimal('0.0001')


def _sku_sales(
    session: Session, filters: ProductSalesFilter, *, every_sku: bool
) -> list[tuple[Any, ...]]:
    """Per SKU: units sold minus returned and Net Sales over the period,
    with its System Quantity now. With `every_sku`, active SKUs that sold
    nothing are there too."""
    start, end = day_bounds(filters.start, filters.end)
    sold = (
        select(
            col(ReceiptLine.sku_id).label('sku_id'),
            func.sum(ReceiptLine.quantity).label('units'),
            func.sum(ReceiptLine.line_total).label('net'),
        )
        .join(Receipt, col(ReceiptLine.receipt_id) == Receipt.id)
        .where(
            Receipt.status == ReceiptStatus.completed,
            col(Receipt.created_at) >= start,
            col(Receipt.created_at) < end,
        )
        .group_by(col(ReceiptLine.sku_id))
        .subquery()
    )
    location_id = stock.resolve_location(session, None)
    units = func.coalesce(sold.c.units, 0)
    net = func.coalesce(sold.c.net, 0)
    columns: list[Any] = [
        Sku,
        Product.name,
        Category.name,
        units,
        net,
        func.coalesce(StockBalance.quantity, 0),
    ]
    conditions: list[Any] = []
    if filters.category_id is not None:
        conditions.append(SubCategory.category_id == filters.category_id)
    if filters.sub_category_id is not None:
        conditions.append(Product.sub_category_id == filters.sub_category_id)
    if every_sku:
        conditions.append(or_(col(Sku.is_active), sold.c.sku_id.is_not(None)))
    query: Any = (
        select(*columns)
        .select_from(Sku)
        .join(Product, col(Sku.product_id) == Product.id)
        .join(SubCategory, col(Product.sub_category_id) == SubCategory.id)
        .join(Category, col(SubCategory.category_id) == Category.id)
        .join(sold, sold.c.sku_id == Sku.id, isouter=every_sku)
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
    if every_sku:
        query = query.order_by(net.desc(), col(Product.name), col(Sku.id))
    else:
        query = query.where(units > 0).order_by(
            units.desc(), net.desc(), col(Product.name), col(Sku.id)
        )
    return list(session.exec(query).all())


def _sku_fields(
    sku: Sku, product_name: str, category_name: str, units: Decimal, net: int
) -> dict[str, Any]:
    return {
        'sku_id': sku.id,
        'product_name': product_name,
        'size': sku.size,
        'color': sku.color,
        'code': sku.code,
        'stock_unit': sku.stock_unit,
        'category_name': category_name,
        'units_sold': units,
        'net_sales': net,
    }


def fast_moving(session: Session, filters: FastMovingFilter) -> FastMoving:
    """SKUs by units sold minus units returned (rule 9)."""
    rows = _sku_sales(session, filters, every_sku=False)[: filters.limit]
    return FastMoving(
        start=filters.start,
        end=filters.end,
        rows=[
            FastMovingRow(**_sku_fields(*row[:5]), stock=row[5])
            for row in rows
        ],
    )


def abc_report(session: Session, filters: ProductSalesFilter) -> AbcReport:
    """ABC Class by Net Sales (rule 10): A until the running share reaches
    80% (the SKU that crosses the line is still A), B until 95%, C the rest,
    including SKUs that sold nothing."""
    rows = _sku_sales(session, filters, every_sku=True)
    total = sum((row[4] for row in rows), 0)
    running = ZERO
    out: list[AbcRow] = []
    for row in rows:
        net = row[4]
        before = running
        share = Decimal(net) / total if total > 0 else ZERO
        running += share
        if net <= 0 or total <= 0:
            abc_class = AbcClass.c
        elif before < A_LINE:
            abc_class = AbcClass.a
        elif before < B_LINE:
            abc_class = AbcClass.b
        else:
            abc_class = AbcClass.c
        out.append(
            AbcRow(
                **_sku_fields(*row[:5]),
                share=share.quantize(SHARE),
                running_share=running.quantize(SHARE),
                abc_class=abc_class,
            )
        )
    classes = []
    for abc_class in AbcClass:
        members = [row for row in out if row.abc_class == abc_class]
        net = sum(row.net_sales for row in members)
        classes.append(
            AbcClassTotal(
                abc_class=abc_class,
                sku_count=len(members),
                net_sales=net,
                share=(Decimal(net) / total).quantize(SHARE)
                if total > 0
                else ZERO,
            )
        )
    return AbcReport(
        start=filters.start,
        end=filters.end,
        net_sales=total,
        classes=classes,
        rows=out,
    )
