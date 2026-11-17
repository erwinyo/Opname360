from datetime import datetime

from sqlalchemy import BigInteger, Index, text
from sqlmodel import Field, SQLModel

from opname360.models._types import enum_type, utc_now
from opname360.models.opname import Resolution


class Shift(SQLModel, table=True):
    """One Cashier at the cash drawer, from the Float to the cash count."""

    __table_args__ = (
        # One drawer per Location: at most one open Shift (rule 1).
        Index(
            'uq_shift_open_per_location',
            'location_id',
            unique=True,
            postgresql_where=text('closed_at IS NULL'),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=30, unique=True)
    location_id: int = Field(foreign_key='location.id')
    cashier_id: int = Field(foreign_key='user.id', index=True)
    # Whole rupiah, like every amount on this table.
    opening_float: int = Field(sa_type=BigInteger)
    opened_at: datetime = Field(default_factory=utc_now)
    closed_at: datetime | None = None
    closed_by: int | None = Field(default=None, foreign_key='user.id')
    expected_cash: int | None = Field(default=None, sa_type=BigInteger)
    counted_cash: int | None = Field(default=None, sa_type=BigInteger)
    # Counted minus expected: below zero the drawer is short.
    cash_variance: int | None = Field(default=None, sa_type=BigInteger)
    resolution: Resolution | None = Field(
        default=None, sa_type=enum_type(Resolution)
    )
    charged_user_id: int | None = Field(default=None, foreign_key='user.id')
    resolved_by: int | None = Field(default=None, foreign_key='user.id')
    resolved_at: datetime | None = None


class ShiftOpen(SQLModel):
    opening_float: int = Field(ge=0)


class ShiftClose(SQLModel):
    counted_cash: int = Field(ge=0)


class ShiftCurrent(SQLModel):
    """The open Shift as the till sees it: no cash figures (blind count)."""

    id: int
    number: str
    cashier_id: int
    cashier_name: str
    opening_float: int
    opened_at: datetime
    # Whether the signed-in user may sell and close in it.
    is_mine: bool


class ShiftPublic(SQLModel):
    id: int
    number: str
    location_name: str
    cashier_id: int
    cashier_name: str
    opening_float: int
    opened_at: datetime
    closed_at: datetime | None
    closed_by_name: str | None
    # While the Shift is open: what the drawer should hold now.
    expected_cash: int
    counted_cash: int | None
    cash_variance: int | None
    needs_resolution: bool
    resolution: Resolution | None
    charged_user_name: str | None
    resolved_by_name: str | None
    resolved_at: datetime | None


class ShiftPage(SQLModel):
    items: list[ShiftPublic]
    total: int


class ShiftFilter(SQLModel):
    needs_resolution: bool = False
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
