from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from opname360.api.deps import SessionDep, require_admin
from opname360.models import (
    Location,
    LocationPublic,
    StockCard,
    StockFilter,
    StockPage,
)
from opname360.services import catalogue
from opname360.services import stock as stock_service


router = APIRouter(
    prefix='/stock', tags=['stock'], dependencies=[Depends(require_admin)]
)


@router.get('/')
def list_stock(
    session: SessionDep, filters: Annotated[StockFilter, Query()]
) -> StockPage:
    return stock_service.list_stock(session, filters)


@router.get('/locations', response_model=list[LocationPublic])
def list_locations(session: SessionDep) -> list[Location]:
    return stock_service.list_locations(session)


@router.get('/skus/{sku_id}/card')
def read_stock_card(
    session: SessionDep,
    sku_id: Annotated[int, Path(ge=1)],
    location_id: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> StockCard:
    sku = catalogue.get_sku(session, sku_id)
    return stock_service.stock_card(
        session, sku, location_id=location_id, offset=offset, limit=limit
    )
