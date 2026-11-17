from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger
from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now


class ReceiptKind(StrEnum):
    sale = 'sale'
    # Customer Return: only lines coming back.
    return_ = 'return'
    # Lines coming back and new lines on one Receipt.
    exchange = 'exchange'


class ReceiptStatus(StrEnum):
    completed = 'completed'
    voided = 'voided'


class ReturnCondition(StrEnum):
    # Back into stock: retur tipe A.
    resellable = 'resellable'
    # Written off: retur tipe B.
    damaged = 'damaged'


# Tables


class Receipt(SQLModel, table=True):
    """One completed till transaction. Amounts are whole rupiah; below zero
    the customer got money back."""

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=30, unique=True)
    kind: ReceiptKind = Field(sa_type=enum_type(ReceiptKind))
    status: ReceiptStatus = Field(
        default=ReceiptStatus.completed, sa_type=enum_type(ReceiptStatus)
    )
    shift_id: int = Field(foreign_key='shift.id', index=True)
    location_id: int = Field(foreign_key='location.id')
    cashier_id: int = Field(foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now, index=True)
    # The Receipt a return or exchange brings goods back from.
    original_receipt_id: int | None = Field(
        default=None, foreign_key='receipt.id', index=True
    )
    # Price times quantity of what was sold, before discounts.
    subtotal: int = Field(default=0, sa_type=BigInteger)
    discount_total: int = Field(default=0, sa_type=BigInteger)
    # What was paid back for returned lines.
    refund_total: int = Field(default=0, sa_type=BigInteger)
    # subtotal - discount_total - refund_total.
    total: int = Field(default=0, sa_type=BigInteger)
    # Handed back from the cash the customer gave.
    change_given: int = Field(default=0, sa_type=BigInteger)
    print_count: int = 0
    void_reason: str | None = Field(default=None, max_length=300)
    voided_by: int | None = Field(default=None, foreign_key='user.id')
    voided_at: datetime | None = None

    lines: list['ReceiptLine'] = Relationship(
        sa_relationship_kwargs={'order_by': 'ReceiptLine.id'}
    )
    payments: list['Payment'] = Relationship(
        sa_relationship_kwargs={'order_by': 'Payment.id'}
    )


class ReceiptLine(SQLModel, table=True):
    """One SKU sold (quantity above zero) or brought back (below zero)."""

    __tablename__ = 'receipt_line'

    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key='receipt.id', index=True)
    sku_id: int = Field(foreign_key='sku.id', index=True)
    quantity: Decimal = Field(max_digits=14, decimal_places=3)
    # The Selling Price at that moment (the original's, for a return).
    unit_price: int = Field(sa_type=BigInteger)
    # Signed like the quantity. Price times quantity, minus this, is the
    # line total.
    discount: int = Field(default=0, sa_type=BigInteger)
    line_total: int = Field(sa_type=BigInteger)
    # What one unit cost when it left stock (or came back at).
    unit_cogs: Decimal = Field(max_digits=18, decimal_places=4)
    original_line_id: int | None = Field(
        default=None, foreign_key='receipt_line.id', index=True
    )
    condition: ReturnCondition | None = Field(
        default=None, sa_type=enum_type(ReturnCondition)
    )


class Payment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int = Field(foreign_key='receipt.id', index=True)
    payment_method_id: int = Field(foreign_key='payment_method.id')
    # What the business kept: change is already taken off; below zero is
    # money paid back.
    amount: int = Field(sa_type=BigInteger)
    reference: str | None = Field(default=None, max_length=100)


# Requests and responses


class TillSku(SQLModel):
    """A SKU as the till shows it: no costs."""

    id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
    selling_price: int


class CartLine(SQLModel):
    sku_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class Cart(SQLModel):
    lines: list[CartLine] = Field(default=[], max_length=500)


class QuotedLine(SQLModel):
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    stock_unit: str
    quantity: Decimal
    unit_price: int
    promotion_name: str | None
    discount: int
    line_total: int


class Quote(SQLModel):
    lines: list[QuotedLine]
    subtotal: int
    discount_total: int
    refund_total: int
    total: int


class PaymentIn(SQLModel):
    payment_method_id: int
    # What the customer handed over with this method.
    amount: int = Field(gt=0)
    reference: str | None = Field(default=None, max_length=100)
    # Non-cash: the Cashier saw the money arrive.
    confirmed: bool = False


class ReceiptCreate(Cart):
    payments: list[PaymentIn] = Field(default=[], max_length=10)
    # The total the customer was shown; a price change in between stops
    # the sale.
    expected_total: int


class ReceiptLinePublic(SQLModel):
    id: int
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    stock_unit: str
    quantity: Decimal
    unit_price: int
    promotion_name: str | None
    discount: int
    line_total: int
    original_line_id: int | None
    condition: ReturnCondition | None


class PaymentPublic(SQLModel):
    payment_method_id: int
    method_name: str
    is_cash: bool
    amount: int
    reference: str | None


class ReceiptPublic(SQLModel):
    id: int
    number: str
    kind: ReceiptKind
    status: ReceiptStatus
    shift_id: int
    shift_number: str
    cashier_name: str
    created_at: datetime
    original_receipt_id: int | None
    original_receipt_number: str | None
    subtotal: int
    discount_total: int
    refund_total: int
    total: int
    change_given: int
    # Above 1, a printout is a copy.
    print_count: int
    void_reason: str | None
    voided_by_name: str | None
    voided_at: datetime | None
    lines: list[ReceiptLinePublic]
    payments: list[PaymentPublic]
