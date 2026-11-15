from datetime import date, datetime
from decimal import Decimal

from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now
from opname360.models.document import DocumentStatus, ReversalPublic


# Tables


class SupplierReturn(SQLModel, table=True):
    __tablename__ = 'supplier_return'

    id: int | None = Field(default=None, primary_key=True)
    number: str | None = Field(default=None, max_length=30, unique=True)
    status: DocumentStatus = Field(
        default=DocumentStatus.draft, sa_type=enum_type(DocumentStatus)
    )
    goods_receipt_id: int = Field(foreign_key='goods_receipt.id', index=True)
    supplier_id: int = Field(foreign_key='supplier.id', index=True)
    location_id: int = Field(foreign_key='location.id')
    returned_on: date
    note: str | None = Field(default=None, max_length=500)
    # What the Supplier owes back: the receipt's cost of the returned units.
    total_refund: Decimal = Field(default=0, max_digits=20, decimal_places=4)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)
    completed_by: int | None = Field(default=None, foreign_key='user.id')
    completed_at: datetime | None = None

    lines: list['SupplierReturnLine'] = Relationship(
        cascade_delete=True,
        sa_relationship_kwargs={'order_by': 'SupplierReturnLine.id'},
    )


class SupplierReturnLine(SQLModel, table=True):
    __tablename__ = 'supplier_return_line'

    id: int | None = Field(default=None, primary_key=True)
    return_id: int = Field(
        foreign_key='supplier_return.id', index=True, ondelete='CASCADE'
    )
    goods_receipt_line_id: int = Field(
        foreign_key='goods_receipt_line.id', index=True
    )
    sku_id: int = Field(foreign_key='sku.id')
    quantity: Decimal = Field(max_digits=14, decimal_places=3)
    # Per Stock Unit, as on the Goods Receipt.
    unit_cost: Decimal = Field(max_digits=18, decimal_places=4)
    total_refund: Decimal = Field(max_digits=20, decimal_places=4)
    # What the units were worth in stock when they left; set on completion.
    stock_cost: Decimal | None = Field(
        default=None, max_digits=20, decimal_places=4
    )


# Requests and responses


class SupplierReturnLineSave(SQLModel):
    goods_receipt_line_id: int
    # In Stock Units.
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class SupplierReturnSave(SQLModel):
    goods_receipt_id: int
    returned_on: date
    note: str | None = Field(default=None, max_length=500)
    lines: list[SupplierReturnLineSave] = []


class SupplierReturnLinePublic(SQLModel):
    id: int
    goods_receipt_line_id: int
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
    quantity: Decimal
    unit_cost: Decimal
    total_refund: Decimal
    stock_cost: Decimal | None


class SupplierReturnPublic(SQLModel):
    id: int
    number: str | None
    status: DocumentStatus
    goods_receipt_id: int
    goods_receipt_number: str | None
    supplier_id: int
    supplier_name: str
    location_name: str
    returned_on: date
    note: str | None
    total_refund: Decimal
    created_by_name: str | None
    created_at: datetime
    completed_by_name: str | None
    completed_at: datetime | None
    reversal: ReversalPublic | None
    lines: list[SupplierReturnLinePublic]


class SupplierReturnSummary(SQLModel):
    id: int
    number: str | None
    status: DocumentStatus
    supplier_name: str
    goods_receipt_number: str | None
    returned_on: date
    total_refund: Decimal
    line_count: int


class SupplierReturnPage(SQLModel):
    items: list[SupplierReturnSummary]
    total: int


class SupplierReturnFilter(SQLModel):
    status: DocumentStatus | None = None
    goods_receipt_id: int | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
