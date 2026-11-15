from datetime import date, datetime
from decimal import Decimal

from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now
from opname360.models.document import DocumentStatus, ReversalPublic


# Tables


class ProductionReceipt(SQLModel, table=True):
    __tablename__ = 'production_receipt'

    id: int | None = Field(default=None, primary_key=True)
    number: str | None = Field(default=None, max_length=30, unique=True)
    status: DocumentStatus = Field(
        default=DocumentStatus.draft, sa_type=enum_type(DocumentStatus)
    )
    location_id: int = Field(foreign_key='location.id')
    produced_on: date
    note: str | None = Field(default=None, max_length=500)
    total_cost: Decimal = Field(default=0, max_digits=20, decimal_places=4)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)
    completed_by: int | None = Field(default=None, foreign_key='user.id')
    completed_at: datetime | None = None

    lines: list['ProductionReceiptLine'] = Relationship(
        cascade_delete=True,
        sa_relationship_kwargs={'order_by': 'ProductionReceiptLine.id'},
    )


class ProductionReceiptLine(SQLModel, table=True):
    __tablename__ = 'production_receipt_line'

    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int = Field(
        foreign_key='production_receipt.id', index=True, ondelete='CASCADE'
    )
    sku_id: int = Field(foreign_key='sku.id', index=True)
    quantity: Decimal = Field(max_digits=14, decimal_places=3)
    unit_cost: Decimal = Field(max_digits=18, decimal_places=4)
    total_cost: Decimal = Field(max_digits=20, decimal_places=4)


# Requests and responses


class ProductionReceiptLineSave(SQLModel):
    sku_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    # What one Stock Unit cost to make: fabric, tailor, and so on.
    unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class ProductionReceiptSave(SQLModel):
    location_id: int | None = None
    produced_on: date
    note: str | None = Field(default=None, max_length=500)
    lines: list[ProductionReceiptLineSave] = []


class ProductionReceiptLinePublic(SQLModel):
    id: int
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal


class ProductionReceiptPublic(SQLModel):
    id: int
    number: str | None
    status: DocumentStatus
    location_id: int
    location_name: str
    produced_on: date
    note: str | None
    total_cost: Decimal
    created_by_name: str | None
    created_at: datetime
    completed_by_name: str | None
    completed_at: datetime | None
    reversal: ReversalPublic | None
    lines: list[ProductionReceiptLinePublic]


class ProductionReceiptSummary(SQLModel):
    id: int
    number: str | None
    status: DocumentStatus
    produced_on: date
    total_cost: Decimal
    line_count: int


class ProductionReceiptPage(SQLModel):
    items: list[ProductionReceiptSummary]
    total: int


class ProductionReceiptFilter(SQLModel):
    status: DocumentStatus | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
