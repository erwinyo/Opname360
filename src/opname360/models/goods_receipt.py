from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now


class DocumentStatus(StrEnum):
    draft = 'draft'
    completed = 'completed'
    reversed = 'reversed'


class PaymentStatus(StrEnum):
    paid = 'paid'
    owed = 'owed'


# Tables


class GoodsReceipt(SQLModel, table=True):
    __tablename__ = 'goods_receipt'

    id: int | None = Field(default=None, primary_key=True)
    # Given when the receipt is completed, so discarded drafts leave no gaps.
    number: str | None = Field(default=None, max_length=30, unique=True)
    status: DocumentStatus = Field(
        default=DocumentStatus.draft, sa_type=enum_type(DocumentStatus)
    )
    supplier_id: int = Field(foreign_key='supplier.id', index=True)
    location_id: int = Field(foreign_key='location.id')
    received_on: date
    supplier_invoice: str | None = Field(default=None, max_length=50)
    payment_status: PaymentStatus = Field(sa_type=enum_type(PaymentStatus))
    note: str | None = Field(default=None, max_length=500)
    total_cost: Decimal = Field(default=0, max_digits=20, decimal_places=4)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)
    completed_by: int | None = Field(default=None, foreign_key='user.id')
    completed_at: datetime | None = None

    lines: list['GoodsReceiptLine'] = Relationship(
        cascade_delete=True,
        sa_relationship_kwargs={'order_by': 'GoodsReceiptLine.id'},
    )


class GoodsReceiptLine(SQLModel, table=True):
    __tablename__ = 'goods_receipt_line'

    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int = Field(
        foreign_key='goods_receipt.id', index=True, ondelete='CASCADE'
    )
    sku_id: int = Field(foreign_key='sku.id', index=True)
    # Always in Stock Units, whatever was typed.
    quantity: Decimal = Field(max_digits=14, decimal_places=3)
    unit_cost: Decimal = Field(max_digits=18, decimal_places=4)
    total_cost: Decimal = Field(max_digits=20, decimal_places=4)
    # Set when the line was typed in Purchase Packs: 2 box of 12 at Rp 60.000.
    pack_name: str | None = Field(default=None, max_length=20)
    pack_size: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=3
    )
    pack_quantity: Decimal | None = Field(
        default=None, max_digits=14, decimal_places=3
    )
    pack_cost: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=4
    )


# Requests and responses


class GoodsReceiptLineSave(SQLModel):
    sku_id: int
    # In Purchase Packs, with the cost per pack, when `in_packs` is set.
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    in_packs: bool = False


class GoodsReceiptSave(SQLModel):
    """A draft Goods Receipt with all its lines, saved together."""

    supplier_id: int
    location_id: int | None = None
    received_on: date
    supplier_invoice: str | None = Field(default=None, max_length=50)
    payment_status: PaymentStatus = PaymentStatus.paid
    note: str | None = Field(default=None, max_length=500)
    lines: list[GoodsReceiptLineSave] = []


class GoodsReceiptLinePublic(SQLModel):
    id: int
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
    # The SKU's own Purchase Pack, offered as a unit while drafting.
    purchase_pack_name: str | None
    purchase_pack_size: Decimal | None
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    pack_name: str | None
    pack_size: Decimal | None
    pack_quantity: Decimal | None
    pack_cost: Decimal | None


class GoodsReceiptPublic(SQLModel):
    id: int
    number: str | None
    status: DocumentStatus
    supplier_id: int
    supplier_name: str
    location_id: int
    location_name: str
    received_on: date
    supplier_invoice: str | None
    payment_status: PaymentStatus
    note: str | None
    total_cost: Decimal
    created_by_name: str | None
    created_at: datetime
    completed_by_name: str | None
    completed_at: datetime | None
    lines: list[GoodsReceiptLinePublic]


class GoodsReceiptSummary(SQLModel):
    id: int
    number: str | None
    status: DocumentStatus
    supplier_name: str
    received_on: date
    payment_status: PaymentStatus
    total_cost: Decimal
    line_count: int


class GoodsReceiptPage(SQLModel):
    items: list[GoodsReceiptSummary]
    total: int


class GoodsReceiptFilter(SQLModel):
    status: DocumentStatus | None = None
    supplier_id: int | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
