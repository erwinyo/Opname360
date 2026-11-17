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


class Dashboard(SQLModel):
    today: HourlySales


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
