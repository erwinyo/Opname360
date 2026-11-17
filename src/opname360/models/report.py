"""Reports: worked out from Stock Movements, Receipts and Stock Opnames.
Nothing here is a table."""

from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel


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
