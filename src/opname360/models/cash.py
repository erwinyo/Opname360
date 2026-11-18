"""Money that isn't a sale: Cash-outs, cash transfers and supplier payments
(slice 5)."""

from datetime import date, datetime
from typing import Self

from pydantic import model_validator
from sqlalchemy import BigInteger
from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now
from opname360.models.document import DocumentStatus, ReversalPublic


# Tables


class CashOut(SQLModel, table=True):
    """Kas Keluar: an expense paid from a cash or bank account."""

    __tablename__ = 'cash_out'

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=30, unique=True)
    status: DocumentStatus = Field(
        default=DocumentStatus.completed, sa_type=enum_type(DocumentStatus)
    )
    paid_on: date
    paid_from_account_id: int = Field(foreign_key='account.id')
    expense_account_id: int = Field(foreign_key='account.id')
    # Whole rupiah.
    amount: int = Field(sa_type=BigInteger)
    description: str = Field(max_length=300)
    paid_to: str | None = Field(default=None, max_length=100)
    # Paid from the drawer: the Shift it came out of (rule 9).
    shift_id: int | None = Field(
        default=None, foreign_key='shift.id', index=True
    )
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)


class CashTransfer(SQLModel, table=True):
    """Pindah Kas: money from one cash or bank account to another."""

    __tablename__ = 'cash_transfer'

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=30, unique=True)
    status: DocumentStatus = Field(
        default=DocumentStatus.completed, sa_type=enum_type(DocumentStatus)
    )
    transferred_on: date
    from_account_id: int = Field(foreign_key='account.id')
    to_account_id: int = Field(foreign_key='account.id')
    amount: int = Field(sa_type=BigInteger)
    description: str | None = Field(default=None, max_length=300)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)


class SupplierPayment(SQLModel, table=True):
    """Bayar Hutang: one payment to a Supplier, shared over what is owed."""

    __tablename__ = 'supplier_payment'

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=30, unique=True)
    status: DocumentStatus = Field(
        default=DocumentStatus.completed, sa_type=enum_type(DocumentStatus)
    )
    supplier_id: int = Field(foreign_key='supplier.id', index=True)
    paid_on: date
    paid_from_account_id: int = Field(foreign_key='account.id')
    amount: int = Field(sa_type=BigInteger)
    note: str | None = Field(default=None, max_length=300)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)

    lines: list['SupplierPaymentLine'] = Relationship(
        sa_relationship_kwargs={'order_by': 'SupplierPaymentLine.id'}
    )


class SupplierPaymentLine(SQLModel, table=True):
    __tablename__ = 'supplier_payment_line'

    id: int | None = Field(default=None, primary_key=True)
    payment_id: int = Field(foreign_key='supplier_payment.id', index=True)
    # None: the debt entered as an opening balance.
    goods_receipt_id: int | None = Field(
        default=None, foreign_key='goods_receipt.id', index=True
    )
    amount: int = Field(sa_type=BigInteger)


# Cash-outs


class CashOutCreate(SQLModel):
    paid_on: date
    paid_from_account_id: int
    expense_account_id: int
    amount: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=300)
    paid_to: str | None = Field(default=None, max_length=100)


class CashOutPublic(SQLModel):
    id: int
    number: str
    status: DocumentStatus
    paid_on: date
    paid_from_account_id: int
    paid_from_name: str
    expense_account_id: int
    expense_name: str
    amount: int
    description: str
    paid_to: str | None
    shift_id: int | None
    shift_number: str | None
    created_by_name: str | None
    created_at: datetime
    reversal: ReversalPublic | None


class CashOutPage(SQLModel):
    items: list[CashOutPublic]
    total: int


class CashFilter(SQLModel):
    start: date | None = None
    end: date | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


# Cash transfers


class CashTransferCreate(SQLModel):
    transferred_on: date
    from_account_id: int
    to_account_id: int
    amount: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=300)

    @model_validator(mode='after')
    def two_accounts(self) -> Self:
        if self.from_account_id == self.to_account_id:
            raise ValueError('Pilih dua akun yang berbeda.')
        return self


class CashTransferPublic(SQLModel):
    id: int
    number: str
    status: DocumentStatus
    transferred_on: date
    from_account_id: int
    from_name: str
    to_account_id: int
    to_name: str
    amount: int
    description: str | None
    created_by_name: str | None
    created_at: datetime
    reversal: ReversalPublic | None


class CashTransferPage(SQLModel):
    items: list[CashTransferPublic]
    total: int


# Supplier payments and debts


class OwedReceipt(SQLModel):
    """One Goods Receipt still owed, or (no id) the opening balance."""

    goods_receipt_id: int | None
    number: str | None
    received_on: date | None
    supplier_invoice: str | None
    total: int
    returned: int
    paid: int
    owed: int


class SupplierDebt(SQLModel):
    supplier_id: int
    supplier_name: str
    owed: int
    receipts: list[OwedReceipt]


class SupplierPaymentLineIn(SQLModel):
    goods_receipt_id: int | None = None
    amount: int = Field(gt=0)


class SupplierPaymentCreate(SQLModel):
    supplier_id: int
    paid_on: date
    paid_from_account_id: int | None = None
    note: str | None = Field(default=None, max_length=300)
    lines: list[SupplierPaymentLineIn] = Field(min_length=1, max_length=200)


class SupplierPaymentLinePublic(SQLModel):
    goods_receipt_id: int | None
    goods_receipt_number: str | None
    amount: int


class SupplierPaymentPublic(SQLModel):
    id: int
    number: str
    status: DocumentStatus
    supplier_id: int
    supplier_name: str
    paid_on: date
    paid_from_account_id: int
    paid_from_name: str
    amount: int
    note: str | None
    created_by_name: str | None
    created_at: datetime
    lines: list[SupplierPaymentLinePublic]
    reversal: ReversalPublic | None


class SupplierPaymentPage(SQLModel):
    items: list[SupplierPaymentPublic]
    total: int
