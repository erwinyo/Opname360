"""Reports: worked out from Stock Movements, Receipts and Stock Opnames.
Nothing here is a table."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from opname360.models.receipt import ReceiptKind


# Laporan Stok Harian


class DailyStockFilter(SQLModel):
    day: date
    category_id: int | None = None
    sub_category_id: int | None = None
    location_id: int | None = None


class StockFlow(SQLModel):
    """One Shop Day of stock: opening + in - out = closing."""

    opening: Decimal
    quantity_in: Decimal
    quantity_out: Decimal
    closing: Decimal
    # The Stock Value after the last Stock Movement of the day.
    closing_value: Decimal


class DailyStockRow(StockFlow):
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    stock_unit: str


class DailyStockSubCategory(StockFlow):
    id: int
    name: str
    rows: list[DailyStockRow]


class DailyStockCategory(StockFlow):
    id: int
    name: str
    sub_categories: list[DailyStockSubCategory]


class DailyStock(StockFlow):
    """Every SKU that had stock or moved by the end of the day."""

    day: date
    location_name: str
    categories: list[DailyStockCategory]


# Penjualan, Laba Kotor per Jam and the Dasbor


class SalesFigures(SQLModel):
    """Net Sales and Gross Profit over a stretch of time (rules 1-3).

    A figure that doesn't apply to a grouping is None: a Payment Method has
    no discounts, and COGS belongs to goods, not to a Cashier or a method.
    """

    receipt_count: int
    # Price times quantity of what was sold.
    gross_sales: int | None
    discounts: int | None
    # Paid back for returned goods.
    refunds: int | None
    net_sales: int
    # Sold goods at cost, less returned goods, plus Negative Stock cost
    # adjustments (costing rule 6).
    cogs: Decimal | None
    gross_profit: Decimal | None


class SalesGroupBy(StrEnum):
    day = 'day'
    cashier = 'cashier'
    payment_method = 'payment_method'
    category = 'category'


class SalesFilter(SQLModel):
    start: date
    end: date
    group_by: SalesGroupBy = SalesGroupBy.day

    @model_validator(mode='after')
    def a_real_period(self) -> Self:
        if self.end < self.start:
            raise ValueError('Tanggal akhir sebelum tanggal awal.')
        if (self.end - self.start).days > 366:
            raise ValueError('Periode paling lama satu tahun.')
        return self


class SalesRow(SalesFigures):
    # The day ("2026-11-17") or the id of the Cashier, method or Category.
    key: str
    label: str


class SalesReport(SQLModel):
    start: date
    end: date
    group_by: SalesGroupBy
    rows: list[SalesRow]
    total: SalesFigures


class HourFigures(SalesFigures):
    # 0-23, in the shop's timezone.
    hour: int


class HourlySales(SalesFigures):
    """One Shop Day: its 24 hours add up to its totals (rule 4)."""

    day: date
    hours: list[HourFigures]


class SalesReceiptFilter(SQLModel):
    """The Receipts behind one row of Penjualan."""

    start: date
    end: date
    cashier_id: int | None = None
    payment_method_id: int | None = None
    category_id: int | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class SalesReceipt(SQLModel):
    id: int
    number: str
    kind: ReceiptKind
    created_at: datetime
    cashier_name: str
    # The Receipt's total; for a method or Category only its part.
    amount: int


class SalesReceiptPage(SQLModel):
    items: list[SalesReceipt]
    total: int


# Fast Moving and Kontribusi Omzet


class ProductSalesFilter(SQLModel):
    start: date
    end: date
    category_id: int | None = None
    sub_category_id: int | None = None

    @model_validator(mode='after')
    def a_real_period(self) -> Self:
        if self.end < self.start:
            raise ValueError('Tanggal akhir sebelum tanggal awal.')
        return self


class FastMovingFilter(ProductSalesFilter):
    limit: int = Field(default=50, ge=1, le=500)


class SkuSales(SQLModel):
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    stock_unit: str
    category_name: str
    # Sold minus returned over the period.
    units_sold: Decimal
    net_sales: int


class FastMovingRow(SkuSales):
    # The System Quantity now.
    stock: Decimal


class FastMoving(SQLModel):
    start: date
    end: date
    rows: list[FastMovingRow]


class AbcClass(StrEnum):
    a = 'A'
    b = 'B'
    c = 'C'


class AbcRow(SkuSales):
    # Fractions of the period's Net Sales: 0.1234 is 12,34%.
    share: Decimal
    running_share: Decimal
    abc_class: AbcClass


class AbcClassTotal(SQLModel):
    abc_class: AbcClass
    sku_count: int
    net_sales: int
    share: Decimal


class AbcReport(SQLModel):
    start: date
    end: date
    net_sales: int
    classes: list[AbcClassTotal]
    rows: list[AbcRow]


# Selisih Opname


class VarianceGroupBy(StrEnum):
    sku = 'sku'
    reason = 'reason'
    resolution = 'resolution'


class VarianceFilter(ProductSalesFilter):
    group_by: VarianceGroupBy = VarianceGroupBy.sku


class VarianceFigures(SQLModel):
    """Variances of approved Stock Opnames. Quantities and values of a
    Shortage are positive; net value is surplus minus shortage."""

    line_count: int
    shortage_quantity: Decimal
    shortage_value: Decimal
    surplus_quantity: Decimal
    surplus_value: Decimal
    net_value: Decimal


class VarianceRow(VarianceFigures):
    # A SKU id, a Shortage reason, a Variance Resolution, or "surplus".
    key: str
    label: str
    code: str | None = None
    stock_unit: str | None = None


class VarianceReport(SQLModel):
    start: date
    end: date
    group_by: VarianceGroupBy
    rows: list[VarianceRow]
    total: VarianceFigures


# The dashboard's attention list


class VoidToday(SQLModel):
    id: int
    number: str
    cashier_name: str
    reason: str | None
    total: int


class Attention(SQLModel):
    negative_stock: int
    voids_today: list[VoidToday]
    opnames_waiting: int
    shifts_waiting: int
    # Medicine past its expiry date still in stock (slice 6).
    expired_batches: int


class Dashboard(SQLModel):
    today: HourlySales
    attention: Attention


# Kedaluwarsa (slice 6)


class ExpiryFilter(SQLModel):
    # Batches that expire within this many days, plus those already expired.
    days: int = Field(default=90, ge=1, le=365)


class ExpiryRow(SQLModel):
    batch_id: int
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    stock_unit: str
    batch_number: str
    expires_on: date
    expired: bool
    quantity: Decimal
    # At the SKU's average cost.
    value: Decimal


class ExpiryReport(SQLModel):
    days: int
    # The one that expires first first.
    rows: list[ExpiryRow]
    expired_value: Decimal
    expiring_value: Decimal
