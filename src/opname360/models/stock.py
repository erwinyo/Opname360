from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlmodel import Field, SQLModel

from opname360.models._types import enum_type, utc_now


class MovementReason(StrEnum):
    goods_receipt = 'goods_receipt'
    production_receipt = 'production_receipt'
    supplier_return = 'supplier_return'
    reversal = 'reversal'
    sale = 'sale'
    # Back from a customer, Resellable or Damaged.
    customer_return = 'customer_return'
    # A Damaged Return leaving stock again at once.
    write_off = 'write_off'
    # A Variance corrected by an approved Stock Opname.
    opname = 'opname'
    # Opening stock from the Opening Opname.
    opening = 'opening'
    # Quantity 0: stock value corrected without goods moving (costing rule 6).
    cost_adjustment = 'cost_adjustment'


# Tables


class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True)


class StockBalance(SQLModel, table=True):
    """What one SKU has at one Location now. Locked while a movement is written."""

    __tablename__ = 'stock_balance'

    sku_id: int = Field(foreign_key='sku.id', primary_key=True)
    location_id: int = Field(foreign_key='location.id', primary_key=True)
    quantity: Decimal = Field(default=0, max_digits=14, decimal_places=3)
    value: Decimal = Field(default=0, max_digits=20, decimal_places=4)


class StockMovement(SQLModel, table=True):
    """Append-only: one change to a SKU's stock, with the balance after it."""

    __tablename__ = 'stock_movement'

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key='sku.id', index=True)
    location_id: int = Field(foreign_key='location.id', index=True)
    reason: MovementReason = Field(sa_type=enum_type(MovementReason))
    # Signed: positive in, negative out.
    quantity: Decimal = Field(max_digits=14, decimal_places=3)
    unit_cost: Decimal = Field(max_digits=18, decimal_places=4)
    # Signed change in Stock Value.
    value: Decimal = Field(max_digits=20, decimal_places=4)
    quantity_after: Decimal = Field(max_digits=14, decimal_places=3)
    value_after: Decimal = Field(max_digits=20, decimal_places=4)
    document_type: str = Field(max_length=30)
    document_id: int
    document_number: str = Field(max_length=30)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now, index=True)


class CostLayer(SQLModel, table=True):
    """FIFO only: what is left of one delivery, at its own unit cost."""

    __tablename__ = 'cost_layer'

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key='sku.id', index=True)
    location_id: int = Field(foreign_key='location.id')
    movement_id: int = Field(foreign_key='stock_movement.id')
    unit_cost: Decimal = Field(max_digits=18, decimal_places=4)
    quantity_remaining: Decimal = Field(max_digits=14, decimal_places=3)
    received_at: datetime = Field(default_factory=utc_now)


class DocumentCounter(SQLModel, table=True):
    """The last running number given out per document prefix and month."""

    __tablename__ = 'document_counter'

    prefix: str = Field(primary_key=True, max_length=10)
    period: str = Field(primary_key=True, max_length=4)
    last_number: int = 0


# Requests and responses


class LocationPublic(SQLModel):
    id: int
    name: str


class StockFilter(SQLModel):
    search: str | None = Field(default=None, max_length=100)
    category_id: int | None = None
    sub_category_id: int | None = None
    location_id: int | None = None
    negative_only: bool = False
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class StockRow(SQLModel):
    sku_id: int
    product_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
    is_active: bool
    category_name: str
    sub_category_name: str
    quantity: Decimal
    value: Decimal


class StockPage(SQLModel):
    items: list[StockRow]
    total: int
    # Stock Value of everything matching the filter, not just this page.
    total_value: Decimal


class StockCardEntry(SQLModel):
    id: int
    created_at: datetime
    reason: MovementReason
    document_type: str
    document_id: int
    document_number: str
    quantity: Decimal
    unit_cost: Decimal
    value: Decimal
    quantity_after: Decimal
    value_after: Decimal
    created_by_name: str | None


class StockCard(SQLModel):
    sku: StockRow
    location: LocationPublic
    items: list[StockCardEntry]
    total: int
