from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from opname360.models._types import utc_now


class Batch(SQLModel, table=True):
    """Medicine: units of one SKU sharing a batch number and expiry date.

    Its quantity at a Location is the sum of its Stock Movements there.
    """

    __table_args__ = (UniqueConstraint('sku_id', 'number'),)

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key='sku.id', index=True, ondelete='CASCADE')
    number: str = Field(max_length=50)
    expires_on: date
    created_at: datetime = Field(default_factory=utc_now)


class BatchStock(SQLModel):
    id: int
    number: str
    expires_on: date
    quantity: Decimal
    # Expired once the day after `expires_on` begins.
    expired: bool
