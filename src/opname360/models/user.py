from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from opname360.models._types import enum_type, utc_now


class Role(StrEnum):
    owner = 'owner'
    admin = 'admin'
    cashier = 'cashier'


class UserBase(SQLModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        regex=r'^[A-Za-z0-9._-]+$',
        unique=True,
        index=True,
    )
    full_name: str = Field(min_length=1, max_length=100)
    role: Role = Field(sa_type=enum_type(Role))
    is_active: bool = True


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password_hash: str
    failed_logins: int = 0
    locked_until: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(SQLModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    is_active: bool | None = None


class PasswordReset(SQLModel):
    password: str = Field(min_length=8, max_length=128)


class UserPublic(UserBase):
    id: int
    created_at: datetime


class LoginRequest(SQLModel):
    username: str
    password: str


class UserSession(SQLModel, table=True):
    __tablename__ = 'user_session'

    token_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key='user.id', index=True, ondelete='CASCADE')
    created_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime = Field(default_factory=utc_now)
