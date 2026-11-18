from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger
from sqlmodel import Field, SQLModel

from opname360.models._types import enum_type, utc_now


class ChargeStatus(StrEnum):
    outstanding = 'outstanding'
    # Paid back or deducted from salary: slice 5.
    settled = 'settled'
    # Its Stock Opname was reversed before it was settled.
    cancelled = 'cancelled'


class EmployeeCharge(SQLModel, table=True):
    """A Shortage that a named employee owes back to the business."""

    __tablename__ = 'employee_charge'

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id', index=True)
    # Whole rupiah.
    amount: int = Field(sa_type=BigInteger)
    status: ChargeStatus = Field(
        default=ChargeStatus.outstanding, sa_type=enum_type(ChargeStatus)
    )
    description: str = Field(max_length=300)
    source_type: str = Field(max_length=30)
    source_id: int
    source_number: str = Field(max_length=30)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)
    cancelled_at: datetime | None = None
    settled_at: datetime | None = None
    settled_by: int | None = Field(default=None, foreign_key='user.id')
    # Deducted from salary rather than paid back.
    settled_by_salary: bool | None = None


class EmployeeChargePublic(SQLModel):
    id: int
    user_id: int
    user_name: str
    amount: int
    status: ChargeStatus
    description: str
    source_type: str
    source_id: int
    source_number: str
    created_by_name: str | None
    created_at: datetime
    settled_at: datetime | None
    settled_by_salary: bool | None


class ChargeSettle(SQLModel):
    by_salary: bool = False
    # Paid back in cash: the account it went into, Kas Besar if not given.
    account_id: int | None = None


class EmployeeChargePage(SQLModel):
    items: list[EmployeeChargePublic]
    total: int


class EmployeeChargeFilter(SQLModel):
    user_id: int | None = None
    status: ChargeStatus | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class EmployeeChargeTotal(SQLModel):
    """What one employee still owes."""

    user_id: int
    full_name: str
    outstanding_amount: int
    outstanding_count: int
