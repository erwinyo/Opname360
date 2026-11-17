from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from opname360.api.deps import SessionDep, require_admin
from opname360.models import DailyStock, DailyStockFilter
from opname360.services import excel, reports


XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
EXCEL: dict[int | str, dict[str, Any]] = {200: {'content': {XLSX: {}}}}

# Rule 13: the Owner and the Admin see every report; a Cashier none.
router = APIRouter(
    prefix='/reports', tags=['reports'], dependencies=[Depends(require_admin)]
)


def excel_file(data: bytes, filename: str) -> Response:
    return Response(
        data,
        media_type=XLSX,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/daily-stock')
def daily_stock(
    session: SessionDep, filters: Annotated[DailyStockFilter, Query()]
) -> DailyStock:
    return reports.daily_stock(session, filters)


@router.get('/daily-stock/excel', response_class=Response, responses=EXCEL)
def daily_stock_excel(
    session: SessionDep, filters: Annotated[DailyStockFilter, Query()]
) -> Response:
    report = reports.daily_stock(session, filters)
    return excel_file(
        excel.daily_stock(report), f'stok-harian-{filters.day}.xlsx'
    )
