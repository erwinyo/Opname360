from datetime import datetime

from sqlmodel import Field, SQLModel

from opname360.models._types import utc_now


class ActivityLog(SQLModel, table=True):
    __tablename__ = 'activity_log'

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None, foreign_key='user.id', index=True
    )
    action: str = Field(max_length=50, index=True)
    entity_type: str | None = Field(default=None, max_length=50)
    entity_id: int | None = None
    summary: str = Field(max_length=500)
    created_at: datetime = Field(default_factory=utc_now, index=True)
