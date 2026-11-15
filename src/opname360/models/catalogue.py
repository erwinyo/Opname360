from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import model_validator
from sqlalchemy import BigInteger, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from opname360.models._types import enum_type, utc_now


class CostingMethod(StrEnum):
    moving_average = 'moving_average'
    fifo = 'fifo'


# Tables


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True)
    costing_method: CostingMethod = Field(sa_type=enum_type(CostingMethod))

    sub_categories: list['SubCategory'] = Relationship(
        back_populates='category',
        cascade_delete=True,
        sa_relationship_kwargs={'order_by': 'SubCategory.name'},
    )


class SubCategory(SQLModel, table=True):
    __tablename__ = 'sub_category'
    __table_args__ = (UniqueConstraint('category_id', 'name'),)

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(
        foreign_key='category.id', index=True, ondelete='CASCADE'
    )
    name: str = Field(max_length=100)

    category: Category = Relationship(back_populates='sub_categories')
    products: list['Product'] = Relationship(back_populates='sub_category')


class Product(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('sub_category_id', 'name'),)

    id: int | None = Field(default=None, primary_key=True)
    sub_category_id: int = Field(foreign_key='sub_category.id', index=True)
    name: str = Field(max_length=200, index=True)

    sub_category: SubCategory = Relationship(back_populates='products')
    skus: list['Sku'] = Relationship(
        back_populates='product',
        cascade_delete=True,
        sa_relationship_kwargs={'order_by': 'Sku.id'},
    )


class Sku(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(
        foreign_key='product.id', index=True, ondelete='CASCADE'
    )
    code: str = Field(max_length=50, unique=True)
    barcode: str = Field(max_length=64, unique=True)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    stock_unit: str = Field(default='pcs', max_length=20)
    purchase_pack_name: str | None = Field(default=None, max_length=20)
    purchase_pack_size: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=3
    )
    # Whole rupiah.
    selling_price: int = Field(sa_type=BigInteger)
    is_active: bool = True
    # What one Stock Unit cost the last time goods came in.
    latest_unit_cost: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=4
    )
    created_at: datetime = Field(default_factory=utc_now)

    product: Product = Relationship(back_populates='skus')
    price_changes: list['SkuPriceChange'] = Relationship(cascade_delete=True)


class SkuPriceChange(SQLModel, table=True):
    __tablename__ = 'sku_price_change'

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key='sku.id', index=True, ondelete='CASCADE')
    old_price: int | None = Field(default=None, sa_type=BigInteger)
    new_price: int = Field(sa_type=BigInteger)
    changed_by: int | None = Field(default=None, foreign_key='user.id')
    changed_at: datetime = Field(default_factory=utc_now)


# Categories: requests and responses


class CategoryCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    costing_method: CostingMethod = CostingMethod.moving_average


class CategoryUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    costing_method: CostingMethod | None = None


class SubCategorySave(SQLModel):
    name: str = Field(min_length=1, max_length=100)


class SubCategoryPublic(SQLModel):
    id: int
    category_id: int
    name: str
    product_count: int


class CategoryPublic(SQLModel):
    id: int
    name: str
    costing_method: CostingMethod
    sub_categories: list[SubCategoryPublic]


# Products and SKUs: requests and responses


class SkuSave(SQLModel):
    """One SKU row of a Product form. Without an `id` it is a new SKU."""

    id: int | None = None
    code: str | None = Field(default=None, max_length=50)
    barcode: str | None = Field(default=None, max_length=64)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    stock_unit: str = Field(default='pcs', min_length=1, max_length=20)
    purchase_pack_name: str | None = Field(default=None, max_length=20)
    purchase_pack_size: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=3
    )
    selling_price: int = Field(ge=0)
    is_active: bool = True

    @model_validator(mode='after')
    def pack_has_name_and_size(self) -> Self:
        has_name = bool(
            self.purchase_pack_name and self.purchase_pack_name.strip()
        )
        if has_name != (self.purchase_pack_size is not None):
            raise ValueError(
                'A purchase pack needs both a name and a size, or neither.'
            )
        return self


class ProductSave(SQLModel):
    """A Product with all its SKUs, saved together."""

    name: str = Field(min_length=1, max_length=200)
    sub_category_id: int
    skus: list[SkuSave] = Field(min_length=1)


class SkuPublic(SQLModel):
    id: int
    product_id: int
    code: str
    barcode: str
    size: str | None
    color: str | None
    stock_unit: str
    purchase_pack_name: str | None
    purchase_pack_size: Decimal | None
    selling_price: int
    is_active: bool
    latest_unit_cost: Decimal | None


class ProductPublic(SQLModel):
    id: int
    name: str
    sub_category_id: int
    sub_category_name: str
    category_id: int
    category_name: str
    skus: list[SkuPublic]


class ProductPage(SQLModel):
    items: list[ProductPublic]
    total: int


class ProductFilter(SQLModel):
    search: str | None = Field(default=None, max_length=100)
    category_id: int | None = None
    sub_category_id: int | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class SkuPriceChangePublic(SQLModel):
    id: int
    old_price: int | None
    new_price: int
    changed_by_name: str | None
    changed_at: datetime


class SkuOption(SQLModel):
    """A SKU as offered when scanning or searching to add a document line."""

    id: int
    product_name: str
    size: str | None
    color: str | None
    code: str
    barcode: str
    stock_unit: str
    purchase_pack_name: str | None
    purchase_pack_size: Decimal | None
    selling_price: int
    latest_unit_cost: Decimal | None
