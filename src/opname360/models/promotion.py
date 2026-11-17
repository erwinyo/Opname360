from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, model_validator
from sqlalchemy import BigInteger
from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now


class DiscountKind(StrEnum):
    percentage = 'percentage'
    # Rupiah off each unit.
    fixed = 'fixed'


class TargetKind(StrEnum):
    skus = 'skus'
    products = 'products'
    sub_categories = 'sub_categories'
    categories = 'categories'


class PromotionStatus(StrEnum):
    upcoming = 'upcoming'
    running = 'running'
    ended = 'ended'


# Tables


class Promotion(SQLModel, table=True):
    """A discount that applies by itself to its targets during its period."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    discount_kind: DiscountKind = Field(sa_type=enum_type(DiscountKind))
    # Percent (1-100) or whole rupiah per unit.
    value: int = Field(sa_type=BigInteger)
    target_kind: TargetKind = Field(sa_type=enum_type(TargetKind))
    starts_at: datetime
    # Exclusive: the Promotion stops at this moment.
    ends_at: datetime
    created_by: int | None = Field(default=None, foreign_key='user.id')
    created_at: datetime = Field(default_factory=utc_now)

    targets: list['PromotionTarget'] = Relationship(cascade_delete=True)


class PromotionTarget(SQLModel, table=True):
    """One SKU, Product, Sub-category or Category, by its id."""

    __tablename__ = 'promotion_target'

    promotion_id: int = Field(
        foreign_key='promotion.id', primary_key=True, ondelete='CASCADE'
    )
    target_id: int = Field(primary_key=True)


# Requests and responses


class PromotionSave(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    discount_kind: DiscountKind
    value: int = Field(gt=0)
    target_kind: TargetKind
    target_ids: list[int] = Field(min_length=1, max_length=2000)
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode='after')
    def sensible(self) -> Self:
        if self.discount_kind == DiscountKind.percentage and self.value > 100:
            raise ValueError('A percentage is at most 100.')
        if self.ends_at <= self.starts_at:
            raise ValueError('A Promotion must end after it starts.')
        return self


class PromotionTargetPublic(SQLModel):
    id: int
    label: str


class PromotionPublic(SQLModel):
    id: int
    name: str
    discount_kind: DiscountKind
    value: int
    target_kind: TargetKind
    targets: list[PromotionTargetPublic]
    starts_at: datetime
    ends_at: datetime
    status: PromotionStatus
    # Already on a Receipt: it can only be ended early.
    used: bool
    created_by_name: str | None
    created_at: datetime


class PromotionPage(SQLModel):
    items: list[PromotionPublic]
    total: int


class PromotionFilter(SQLModel):
    status: PromotionStatus | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
