from datetime import datetime

from sqlmodel import Field, SQLModel

from opname360.models._types import utc_now


class SupplierBase(SQLModel):
    name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)


class Supplier(SupplierBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=150, unique=True)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None


class SupplierPublic(SupplierBase):
    id: int
    is_active: bool
