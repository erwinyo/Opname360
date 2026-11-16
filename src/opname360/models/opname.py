from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import model_validator
from sqlalchemy import BigInteger, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now
from opname360.models.document import ReversalPublic
from opname360.models.user import Role


class OpnameStatus(StrEnum):
    counting = 'counting'
    review = 'review'
    approved = 'approved'
    cancelled = 'cancelled'
    reversed = 'reversed'


class OpnameScope(StrEnum):
    everything = 'everything'
    categories = 'categories'
    sub_categories = 'sub_categories'
    skus = 'skus'


class ShortageReason(StrEnum):
    damaged = 'damaged'
    lost = 'lost'
    miscounted = 'miscounted'
    unknown = 'unknown'


class Resolution(StrEnum):
    company_loss = 'company_loss'
    employee_charge = 'employee_charge'


# Tables


class StockOpname(SQLModel, table=True):
    __tablename__ = 'stock_opname'

    id: int | None = Field(default=None, primary_key=True)
    # Given when the session opens: Checkers see it from the start.
    number: str = Field(max_length=30, unique=True)
    location_id: int = Field(foreign_key='location.id')
    scope: OpnameScope = Field(sa_type=enum_type(OpnameScope))
    # What the Scope was, in words: "Seragam, ATK" or "12 SKU pilihan".
    scope_label: str = Field(max_length=300)
    is_opening: bool = False
    status: OpnameStatus = Field(
        default=OpnameStatus.counting, sa_type=enum_type(OpnameStatus)
    )
    note: str | None = Field(default=None, max_length=500)
    opened_by: int | None = Field(default=None, foreign_key='user.id')
    opened_at: datetime = Field(default_factory=utc_now)
    counting_closed_by: int | None = Field(default=None, foreign_key='user.id')
    counting_closed_at: datetime | None = None
    approved_by: int | None = Field(default=None, foreign_key='user.id')
    approved_at: datetime | None = None
    cancelled_by: int | None = Field(default=None, foreign_key='user.id')
    cancelled_at: datetime | None = None

    lines: list['OpnameLine'] = Relationship(
        cascade_delete=True,
        sa_relationship_kwargs={'order_by': 'OpnameLine.id'},
    )


class OpnameChecker(SQLModel, table=True):
    """A user assigned to count in one session."""

    __tablename__ = 'stock_opname_checker'

    opname_id: int = Field(
        foreign_key='stock_opname.id', primary_key=True, ondelete='CASCADE'
    )
    user_id: int = Field(foreign_key='user.id', primary_key=True)


class OpnameLine(SQLModel, table=True):
    """One SKU in Scope. Counted once it has an active Count Entry."""

    __tablename__ = 'stock_opname_line'
    __table_args__ = (UniqueConstraint('opname_id', 'sku_id'),)

    id: int | None = Field(default=None, primary_key=True)
    opname_id: int = Field(
        foreign_key='stock_opname.id', index=True, ondelete='CASCADE'
    )
    sku_id: int = Field(foreign_key='sku.id', index=True)
    # The System Quantity when the first Count Entry came in.
    system_quantity: Decimal | None = Field(
        default=None, max_digits=14, decimal_places=3
    )
    first_counted_at: datetime | None = None
    # The sum of the active Count Entries.
    physical_quantity: Decimal = Field(
        default=0, max_digits=14, decimal_places=3
    )
    moved_while_counting: bool = False
    # Sent back to be counted again while the session is in Review.
    recount: bool = False
    # Entered by hand: the opening cost in an Opening Opname, or the cost of
    # a Surplus of a SKU that has never had one.
    unit_cost: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=4
    )
    shortage_reason: ShortageReason | None = Field(
        default=None, sa_type=enum_type(ShortageReason)
    )
    resolution: Resolution | None = Field(
        default=None, sa_type=enum_type(Resolution)
    )
    charged_user_id: int | None = Field(default=None, foreign_key='user.id')
    # Whole rupiah; without it the charge is the Shortage at cost.
    charge_amount: int | None = Field(default=None, sa_type=BigInteger)
    # Set on approval: the Stock Value its Stock Movement added or removed.
    adjusted_value: Decimal | None = Field(
        default=None, max_digits=20, decimal_places=4
    )


class CountEntry(SQLModel, table=True):
    """One scan or typed quantity. A Recount cancels it; nothing deletes it."""

    __tablename__ = 'stock_opname_count'

    id: int | None = Field(default=None, primary_key=True)
    line_id: int = Field(
        foreign_key='stock_opname_line.id', index=True, ondelete='CASCADE'
    )
    quantity: Decimal = Field(max_digits=14, decimal_places=3)
    counted_by: int = Field(foreign_key='user.id', index=True)
    counted_at: datetime = Field(default_factory=utc_now)
    cancelled_by: int | None = Field(default=None, foreign_key='user.id')
    cancelled_at: datetime | None = None


class UnknownBarcode(SQLModel, table=True):
    """A code scanned in a session that matched no SKU."""

    __tablename__ = 'stock_opname_unknown_barcode'

    id: int | None = Field(default=None, primary_key=True)
    opname_id: int = Field(
        foreign_key='stock_opname.id', index=True, ondelete='CASCADE'
    )
    code: str = Field(max_length=64)
    scanned_by: int = Field(foreign_key='user.id')
    scanned_at: datetime = Field(default_factory=utc_now)


# Opening and listing


class OpnameOpen(SQLModel):
    location_id: int | None = None
    scope: OpnameScope = OpnameScope.everything
    # Only the list matching `scope` is used.
    category_ids: list[int] = []
    sub_category_ids: list[int] = []
    sku_ids: list[int] = []
    checker_ids: list[int] = Field(min_length=1)
    is_opening: bool = False
    note: str | None = Field(default=None, max_length=500)


class StaffOption(SQLModel):
    id: int
    full_name: str
    role: Role


class OpnameSummary(SQLModel):
    id: int
    number: str
    status: OpnameStatus
    scope: OpnameScope
    scope_label: str
    is_opening: bool
    location_name: str
    opened_at: datetime
    opened_by_name: str | None
    line_count: int
    counted_count: int


class OpnamePage(SQLModel):
    items: list[OpnameSummary]
    total: int


class OpnameFilter(SQLModel):
    status: OpnameStatus | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


# One session


class UnknownBarcodePublic(SQLModel):
    code: str
    times: int
    last_scanned_by_name: str | None
    last_scanned_at: datetime


class OpnamePublic(SQLModel):
    id: int
    number: str
    status: OpnameStatus
    scope: OpnameScope
    scope_label: str
    is_opening: bool
    location_id: int
    location_name: str
    note: str | None
    opened_by_name: str | None
    opened_at: datetime
    counting_closed_by_name: str | None
    counting_closed_at: datetime | None
    approved_by_name: str | None
    approved_at: datetime | None
    cancelled_by_name: str | None
    cancelled_at: datetime | None
    checkers: list[StaffOption]
    line_count: int
    counted_count: int
    recount_count: int
    # Whether this user sees System Quantities and Variances: only from
    # Review on, and never a Checker of this session (Blind Count).
    revealed: bool
    # Whether this user may review and approve (an Owner or Admin who was not
    # a Checker here).
    can_approve: bool
    # Sent only when revealed. Estimated until approval, actual after.
    shortage_count: int | None
    shortage_value: Decimal | None
    surplus_count: int | None
    surplus_value: Decimal | None
    unknown_barcodes: list[UnknownBarcodePublic]
    reversal: ReversalPublic | None


class LineShow(StrEnum):
    all = 'all'
    uncounted = 'uncounted'
    counted = 'counted'
    # Only once revealed: lines with a Variance, and lines being recounted.
    variance = 'variance'
    # Lines a Surplus or opening stock still needs a unit cost for.
    needs_cost = 'needs_cost'


class OpnameLineFilter(SQLModel):
    show: LineShow = LineShow.all
    search: str | None = Field(default=None, max_length=100)
    offset: int = Field(default=0, ge=0)
    # High enough to print a Berita Acara in one go.
    limit: int = Field(default=50, ge=1, le=2000)


class OpnameLinePublic(SQLModel):
    id: int
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
    counted: bool
    recount: bool
    # The rest is None unless the session is revealed to this user.
    system_quantity: Decimal | None = None
    physical_quantity: Decimal | None = None
    variance: Decimal | None = None
    moved_while_counting: bool | None = None
    # What the Variance is valued at per unit: entered, or by costing rule 5.
    unit_cost: Decimal | None = None
    # A Surplus (or opening stock) with no cost known: one must be entered.
    needs_cost: bool | None = None
    # Estimated until approval, then what the Stock Movement really moved.
    variance_value: Decimal | None = None
    entered_unit_cost: Decimal | None = None
    shortage_reason: ShortageReason | None = None
    resolution: Resolution | None = None
    charged_user_id: int | None = None
    charged_user_name: str | None = None
    charge_amount: int | None = None


class OpnameLinePage(SQLModel):
    items: list[OpnameLinePublic]
    total: int


class ZeroConfirm(SQLModel):
    line_ids: list[int] = Field(min_length=1)


class LineResolutionSave(SQLModel):
    """The approver's decision on one line. Unset fields are cleared."""

    shortage_reason: ShortageReason | None = None
    resolution: Resolution | None = None
    charged_user_id: int | None = None
    charge_amount: int | None = Field(default=None, ge=0)
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=4
    )


# Counting (the Checker's phone)


class CountingSummary(SQLModel):
    id: int
    number: str
    status: OpnameStatus
    scope_label: str
    location_name: str
    opened_at: datetime
    # False while the session waits in Review with nothing to recount.
    can_count: bool


class CountCreate(SQLModel):
    """A scan (code, quantity 1) or a typed quantity for a code or SKU."""

    code: str | None = Field(default=None, max_length=64)
    sku_id: int | None = None
    quantity: Decimal = Field(
        default=Decimal(1), gt=0, max_digits=14, decimal_places=3
    )

    @model_validator(mode='after')
    def code_or_sku(self) -> Self:
        if (self.code is None) == (self.sku_id is None):
            raise ValueError('Send either a code or a sku_id.')
        return self


class MyCountEntry(SQLModel):
    id: int
    sku_id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    stock_unit: str
    quantity: Decimal
    counted_at: datetime


class CountSheet(SQLModel):
    """What one Checker sees: their own entries, never a System Quantity."""

    id: int
    number: str
    status: OpnameStatus
    scope_label: str
    location_name: str
    can_count: bool
    # This Checker's active entries, newest first (at most 200).
    entries: list[MyCountEntry]
    entry_count: int
    sku_count: int


class CountSkuOption(SQLModel):
    """A SKU in Scope, found by name for typing a quantity."""

    id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
