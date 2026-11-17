"""The Ledger (slice 5): accounts and journal entries."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import model_validator
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now


class AccountType(StrEnum):
    asset = 'asset'
    liability = 'liability'
    equity = 'equity'
    revenue = 'revenue'
    cogs = 'cogs'
    expense = 'expense'


class AccountRole(StrEnum):
    """What the system posts to. Each role is played by one account."""

    cash_main = 'cash_main'
    cash_drawer = 'cash_drawer'
    bank = 'bank'
    inventory = 'inventory'
    employee_receivable = 'employee_receivable'
    accounts_payable = 'accounts_payable'
    opening_balance = 'opening_balance'
    retained_earnings = 'retained_earnings'
    sales = 'sales'
    sales_discount = 'sales_discount'
    sales_return = 'sales_return'
    other_income = 'other_income'
    inventory_surplus = 'inventory_surplus'
    cash_over = 'cash_over'
    cogs = 'cogs'
    inventory_shortage = 'inventory_shortage'
    damaged_goods = 'damaged_goods'
    cash_short = 'cash_short'
    production_cost = 'production_cost'
    salary = 'salary'


class EntrySource(StrEnum):
    # Posted by the system when a document took effect.
    document = 'document'
    # Typed in Jurnal Umum.
    manual = 'manual'
    # Saldo Awal.
    opening = 'opening'


# Tables


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=20, unique=True)
    name: str = Field(max_length=100, unique=True)
    type: AccountType = Field(sa_type=enum_type(AccountType))
    # A cash or bank account: money can be paid from it.
    is_cash: bool = False
    # Set when the system posts to it; such an account can't be deleted.
    role: AccountRole | None = Field(
        default=None, unique=True, sa_type=enum_type(AccountRole)
    )
    is_active: bool = True


class JournalEntry(SQLModel, table=True):
    """Balanced and never changed: a mistake is undone by a mirror entry."""

    __tablename__ = 'journal_entry'
    __table_args__ = (
        # A document posts each event once, so backfill can run twice.
        UniqueConstraint('document_type', 'document_id', 'event'),
    )

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=30, unique=True)
    # The Shop Day it belongs to.
    entry_date: date = Field(index=True)
    description: str = Field(max_length=300)
    source: EntrySource = Field(sa_type=enum_type(EntrySource))
    document_type: str | None = Field(default=None, max_length=30)
    document_id: int | None = None
    document_number: str | None = Field(default=None, max_length=30)
    # What happened to the document: complete, open, close, ...
    event: str | None = Field(default=None, max_length=30)
    # The entry this one mirrors.
    reverses_id: int | None = Field(
        default=None, foreign_key='journal_entry.id', unique=True
    )
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)

    lines: list['JournalLine'] = Relationship(
        sa_relationship_kwargs={'order_by': 'JournalLine.id'}
    )


class JournalLine(SQLModel, table=True):
    __tablename__ = 'journal_line'
    __table_args__ = (
        CheckConstraint(
            '(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)',
            name='journal_line_one_side',
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    entry_id: int = Field(foreign_key='journal_entry.id', index=True)
    account_id: int = Field(foreign_key='account.id', index=True)
    debit: Decimal = Field(default=0, max_digits=20, decimal_places=4)
    credit: Decimal = Field(default=0, max_digits=20, decimal_places=4)
    # Hutang Usaha names the Supplier; Piutang Karyawan the employee.
    supplier_id: int | None = Field(default=None, foreign_key='supplier.id')
    user_id: int | None = Field(default=None, foreign_key='user.id')


# Accounts: requests and responses


class AccountSave(SQLModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    type: AccountType
    is_cash: bool = False
    is_active: bool = True

    @model_validator(mode='after')
    def cash_is_an_asset(self) -> Self:
        if self.is_cash and self.type != AccountType.asset:
            raise ValueError('Akun kas atau bank harus berjenis aset.')
        return self


class AccountPublic(SQLModel):
    id: int
    code: str
    name: str
    type: AccountType
    is_cash: bool
    role: AccountRole | None
    is_active: bool
    # Debit minus credit over all time.
    balance: Decimal
    # Whether any journal line uses it: then it can only be deactivated.
    used: bool


class RoleAssign(SQLModel):
    account_id: int


# Journal entries: requests and responses


class JournalLineIn(SQLModel):
    account_id: int
    debit: Decimal = Field(default=0, ge=0, max_digits=20, decimal_places=4)
    credit: Decimal = Field(default=0, ge=0, max_digits=20, decimal_places=4)
    supplier_id: int | None = None
    user_id: int | None = None

    @model_validator(mode='after')
    def one_side(self) -> Self:
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError('Isi debit atau kredit, salah satu saja.')
        return self


class ManualEntryIn(SQLModel):
    entry_date: date
    description: str = Field(min_length=1, max_length=300)
    lines: list[JournalLineIn] = Field(min_length=2, max_length=100)


class JournalLinePublic(SQLModel):
    id: int
    account_id: int
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    supplier_id: int | None
    supplier_name: str | None
    user_id: int | None
    user_name: str | None


class JournalEntryPublic(SQLModel):
    id: int
    number: str
    entry_date: date
    description: str
    source: EntrySource
    document_type: str | None
    document_id: int | None
    document_number: str | None
    event: str | None
    reverses_id: int | None
    reverses_number: str | None
    reversed_by_id: int | None
    reversed_by_number: str | None
    created_by_name: str | None
    created_at: datetime
    total: Decimal
    lines: list[JournalLinePublic]


class JournalFilter(SQLModel):
    start: date | None = None
    end: date | None = None
    account_id: int | None = None
    source: EntrySource | None = None
    search: str | None = Field(default=None, max_length=100)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class JournalPage(SQLModel):
    items: list[JournalEntryPublic]
    total: int


# Buku Besar and Neraca Saldo


class AccountBookFilter(SQLModel):
    start: date
    end: date


class AccountBookLine(SQLModel):
    entry_id: int
    number: str
    entry_date: date
    description: str
    document_type: str | None
    document_id: int | None
    debit: Decimal
    credit: Decimal
    # Debit minus credit, after this line.
    balance: Decimal


class AccountBook(SQLModel):
    account: AccountPublic
    start: date
    end: date
    opening_balance: Decimal
    lines: list[AccountBookLine]
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal


class TrialBalanceRow(SQLModel):
    account_id: int
    code: str
    name: str
    type: AccountType
    debit: Decimal
    credit: Decimal


class TrialBalance(SQLModel):
    on: date
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
