from datetime import datetime
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from opname360.models._types import utc_now


class DocumentStatus(StrEnum):
    draft = 'draft'
    completed = 'completed'
    reversed = 'reversed'


class Reversal(SQLModel, table=True):
    """Cancels one completed document. Its Stock Movements carry its number."""

    __table_args__ = (UniqueConstraint('document_type', 'document_id'),)

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(max_length=30, unique=True)
    document_type: str = Field(max_length=30)
    document_id: int
    reason: str = Field(max_length=300)
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)


class ReversalCreate(SQLModel):
    reason: str = Field(min_length=1, max_length=300)


class ReversalPublic(SQLModel):
    number: str
    reason: str
    created_by_name: str | None
    created_at: datetime
