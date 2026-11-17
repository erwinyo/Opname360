import time

from collections.abc import Iterator
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent

from opname360.api.deps import SessionDep, require_admin
from opname360.models import (
    AbcReport,
    DailyStock,
    DailyStockFilter,
    Dashboard,
    FastMoving,
    FastMovingFilter,
    HourlySales,
    ProductSalesFilter,
    SalesFilter,
    SalesReceiptFilter,
    SalesReceiptPage,
    SalesReport,
    VarianceFilter,
    VarianceReport,
)
from opname360.services import excel, reports


XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
EXCEL: dict[int | str, dict[str, Any]] = {200: {'content': {XLSX: {}}}}
# How often an open dashboard's stream looks for something new.
POLL_SECONDS = 2

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


@router.get('/sales')
def sales(
    session: SessionDep, filters: Annotated[SalesFilter, Query()]
) -> SalesReport:
    return reports.sales_report(session, filters)


@router.get('/sales/excel', response_class=Response, responses=EXCEL)
def sales_excel(
    session: SessionDep, filters: Annotated[SalesFilter, Query()]
) -> Response:
    report = reports.sales_report(session, filters)
    return excel_file(
        excel.sales(report),
        f'penjualan-{filters.start}-{filters.end}-{filters.group_by}.xlsx',
    )


@router.get('/sales/receipts')
def sales_receipts(
    session: SessionDep, filters: Annotated[SalesReceiptFilter, Query()]
) -> SalesReceiptPage:
    return reports.sales_receipts(session, filters)


@router.get('/hourly')
def hourly(session: SessionDep, day: Annotated[date, Query()]) -> HourlySales:
    return reports.hourly_sales(session, day)


@router.get('/hourly/excel', response_class=Response, responses=EXCEL)
def hourly_excel(
    session: SessionDep, day: Annotated[date, Query()]
) -> Response:
    report = reports.hourly_sales(session, day)
    hours = reports.shown_hours(session, report)
    return excel_file(
        excel.hourly(report, hours), f'laba-kotor-per-jam-{day}.xlsx'
    )


@router.get('/fast-moving')
def fast_moving(
    session: SessionDep, filters: Annotated[FastMovingFilter, Query()]
) -> FastMoving:
    return reports.fast_moving(session, filters)


@router.get('/fast-moving/excel', response_class=Response, responses=EXCEL)
def fast_moving_excel(
    session: SessionDep, filters: Annotated[FastMovingFilter, Query()]
) -> Response:
    report = reports.fast_moving(session, filters)
    return excel_file(
        excel.fast_moving(report),
        f'fast-moving-{filters.start}-{filters.end}.xlsx',
    )


@router.get('/abc')
def abc(
    session: SessionDep, filters: Annotated[ProductSalesFilter, Query()]
) -> AbcReport:
    return reports.abc_report(session, filters)


@router.get('/abc/excel', response_class=Response, responses=EXCEL)
def abc_excel(
    session: SessionDep, filters: Annotated[ProductSalesFilter, Query()]
) -> Response:
    report = reports.abc_report(session, filters)
    return excel_file(
        excel.abc(report),
        f'kontribusi-omzet-{filters.start}-{filters.end}.xlsx',
    )


@router.get('/variances')
def variances(
    session: SessionDep, filters: Annotated[VarianceFilter, Query()]
) -> VarianceReport:
    return reports.variances(session, filters)


@router.get('/variances/excel', response_class=Response, responses=EXCEL)
def variances_excel(
    session: SessionDep, filters: Annotated[VarianceFilter, Query()]
) -> Response:
    report = reports.variances(session, filters)
    return excel_file(
        excel.variances(report),
        f'selisih-opname-{filters.start}-{filters.end}-{filters.group_by}.xlsx',
    )


@router.get('/dashboard')
def dashboard(session: SessionDep) -> Dashboard:
    return reports.dashboard(session)


@router.get('/live', response_class=EventSourceResponse)
def live(session: SessionDep) -> Iterator[ServerSentEvent]:
    """Says `changed` whenever something new is recorded, so an open
    dashboard reloads within seconds (rule 8). Only a number goes out: the
    figures themselves are fetched, and checked, as usual."""
    # ponytail: one poll per open dashboard every 2 s; LISTEN/NOTIFY if
    # many screens ever stay open.
    seen = None
    while True:
        latest = reports.latest_activity(session)
        # Hand the connection back between polls.
        session.close()
        if latest != seen:
            seen = latest
            yield ServerSentEvent(data=latest, event='changed')
        time.sleep(POLL_SECONDS)
