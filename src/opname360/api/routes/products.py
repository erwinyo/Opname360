from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    Product,
    ProductFilter,
    ProductPage,
    ProductPublic,
    ProductSave,
    Sku,
    SkuPriceChangePublic,
)
from opname360.services import catalogue


router = APIRouter(
    prefix='/products',
    tags=['products'],
    dependencies=[Depends(require_admin)],
)


def get_product_or_404(
    session: SessionDep, product_id: Annotated[int, Path(ge=1)]
) -> Product:
    return catalogue.get_product(session, product_id)


def get_sku_or_404(
    session: SessionDep, sku_id: Annotated[int, Path(ge=1)]
) -> Sku:
    return catalogue.get_sku(session, sku_id)


ProductDep = Annotated[Product, Depends(get_product_or_404)]
SkuDep = Annotated[Sku, Depends(get_sku_or_404)]


@router.get('/')
def list_products(
    session: SessionDep, filters: Annotated[ProductFilter, Query()]
) -> ProductPage:
    return catalogue.list_products(session, filters)


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_product(
    session: SessionDep, admin: AdminDep, product_in: ProductSave
) -> ProductPublic:
    product = catalogue.create_product(session, product_in, actor=admin)
    return catalogue.product_public(product)


@router.get('/{product_id}')
def read_product(product: ProductDep) -> ProductPublic:
    return catalogue.product_public(product)


@router.put('/{product_id}')
def update_product(
    session: SessionDep,
    admin: AdminDep,
    product: ProductDep,
    product_in: ProductSave,
) -> ProductPublic:
    catalogue.update_product(session, product, product_in, actor=admin)
    return catalogue.product_public(product)


@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    session: SessionDep, admin: AdminDep, product: ProductDep
) -> None:
    catalogue.delete_product(session, product, actor=admin)


@router.get('/skus/{sku_id}/price-changes')
def list_price_changes(
    session: SessionDep, sku: SkuDep
) -> list[SkuPriceChangePublic]:
    return catalogue.list_price_changes(session, sku)
