from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.core.errors import AppError
from opname360.models import (
    ImportPreview,
    ImportResult,
    Product,
    ProductFilter,
    ProductPage,
    ProductPublic,
    ProductSave,
    Sku,
    SkuOption,
    SkuPriceChangePublic,
)
from opname360.services import catalogue, product_import


XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
MAX_UPLOAD = 5 * 1024 * 1024


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


@router.get('/skus/search')
def search_skus(
    session: SessionDep,
    query: Annotated[str, Query(max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SkuOption]:
    return catalogue.search_skus(session, query, limit=limit)


@router.get('/skus')
def list_skus(
    session: SessionDep,
    ids: Annotated[list[int], Query(max_length=500)],
) -> list[SkuOption]:
    """The given SKUs, for printing their labels."""
    return catalogue.skus_by_id(session, ids)


@router.get(
    '/import/template',
    response_class=Response,
    responses={200: {'content': {XLSX: {}}}},
)
def download_import_template() -> Response:
    return Response(
        product_import.template(),
        media_type=XLSX,
        headers={
            'Content-Disposition': (
                'attachment; filename="template-impor-produk.xlsx"'
            )
        },
    )


@router.post('/import/preview')
def preview_import(session: SessionDep, file: UploadFile) -> ImportPreview:
    return product_import.preview(session, _read_upload(file))


@router.post('/import')
def run_import(
    session: SessionDep, admin: AdminDep, file: UploadFile
) -> ImportResult:
    return product_import.run(
        session,
        _read_upload(file),
        filename=file.filename or 'file Excel',
        actor=admin,
    )


def _read_upload(file: UploadFile) -> bytes:
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise AppError('File terlalu besar (paling besar 5 MB).')
    return data


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
