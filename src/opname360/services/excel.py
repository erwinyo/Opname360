"""Excel exports of the reports: the same rows and numbers as on screen
(rule 12), money rounded to whole rupiah as the screens show it."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from opname360.core.formatting import sku_label
from opname360.models import (
    AbcReport,
    DailyStock,
    FastMoving,
    HourlySales,
    SalesFigures,
    SalesGroupBy,
    SalesReport,
    SalesRow,
    StockFlow,
)


MONTHS = (
    'Januari',
    'Februari',
    'Maret',
    'April',
    'Mei',
    'Juni',
    'Juli',
    'Agustus',
    'September',
    'Oktober',
    'November',
    'Desember',
)
MONEY = '#,##0'
PERCENT = '0.0%'


@dataclass
class Column:
    title: str
    width: int = 14
    number_format: str | None = None


# One row of cells, and whether it is a total (bold).
type Row = tuple[list[object], bool]


def rupiah(value: Decimal | int) -> int:
    return int(Decimal(value).quantize(Decimal(1), ROUND_HALF_UP))


def long_date(day: date) -> str:
    """17 November 2026"""
    return f'{day.day} {MONTHS[day.month - 1]} {day.year}'


def workbook(
    title: str, subtitle: str, columns: list[Column], rows: list[Row]
) -> bytes:
    """One sheet: a title, a subtitle, then a table with a frozen header."""
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = title[:31]
    sheet.append([title])
    sheet['A1'].font = Font(bold=True, size=13)
    sheet.append([subtitle])
    sheet.append([])
    sheet.append([column.title for column in columns])
    for cell in sheet[4]:
        cell.font = Font(bold=True)
    for values, bold in rows:
        sheet.append(values)
        if bold:
            for cell in sheet[sheet.max_row]:
                cell.font = Font(bold=True)
    for index, column in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = column.width
        if column.number_format:
            for (cell,) in sheet.iter_rows(
                min_row=5, min_col=index, max_col=index
            ):
                cell.number_format = column.number_format
    sheet.freeze_panes = 'A5'
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def daily_stock(report: DailyStock) -> bytes:
    def flow(part: StockFlow) -> list[object]:
        return [
            part.opening,
            part.quantity_in,
            part.quantity_out,
            part.closing,
            rupiah(part.closing_value),
        ]

    rows: list[Row] = []
    for category in report.categories:
        for sub in category.sub_categories:
            for row in sub.rows:
                rows.append(
                    (
                        [
                            category.name,
                            sub.name,
                            sku_label(row.product_name, row.size, row.color),
                            row.code,
                            row.stock_unit,
                            *flow(row),
                        ],
                        False,
                    )
                )
            rows.append(
                (
                    [category.name, sub.name, 'Subtotal', '', '', *flow(sub)],
                    True,
                )
            )
        rows.append(
            (
                [category.name, '', 'Total kategori', '', '', *flow(category)],
                True,
            )
        )
    rows.append((['', '', 'Total', '', '', *flow(report)], True))
    return workbook(
        'Laporan Stok Harian',
        f'{long_date(report.day)} · {report.location_name}',
        [
            Column('Kategori', 18),
            Column('Sub-kategori', 18),
            Column('Barang', 36),
            Column('Kode', 16),
            Column('Satuan', 8),
            Column('Awal', 10),
            Column('Masuk', 10),
            Column('Keluar', 10),
            Column('Akhir', 10),
            Column('Nilai akhir', 16, MONEY),
        ],
        rows,
    )


GROUP_TITLES = {
    SalesGroupBy.day: 'Tanggal',
    SalesGroupBy.cashier: 'Kasir',
    SalesGroupBy.payment_method: 'Metode pembayaran',
    SalesGroupBy.category: 'Kategori',
}
FIGURE_COLUMNS = [
    Column('Struk', 8),
    Column('Penjualan kotor', 16, MONEY),
    Column('Diskon', 14, MONEY),
    Column('Retur', 14, MONEY),
    Column('Penjualan bersih', 16, MONEY),
    Column('HPP', 16, MONEY),
    Column('Laba kotor', 16, MONEY),
]


def _figures(figures: SalesFigures) -> list[object]:
    def cell(value: Decimal | int | None) -> object:
        return '' if value is None else rupiah(value)

    return [
        figures.receipt_count,
        cell(figures.gross_sales),
        cell(figures.discounts),
        cell(figures.refunds),
        cell(figures.net_sales),
        cell(figures.cogs),
        cell(figures.gross_profit),
    ]


def sales(report: SalesReport) -> bytes:
    def label(row: SalesRow) -> str:
        if report.group_by == SalesGroupBy.day:
            return long_date(date.fromisoformat(row.key))
        return row.label

    rows: list[Row] = [
        ([label(row), *_figures(row)], False) for row in report.rows
    ]
    rows.append((['Total', *_figures(report.total)], True))
    return workbook(
        'Penjualan',
        _period(report.start, report.end),
        [Column(GROUP_TITLES[report.group_by], 24), *FIGURE_COLUMNS],
        rows,
    )


def hourly(report: HourlySales, hours: list[int]) -> bytes:
    by_hour = {figures.hour: figures for figures in report.hours}
    rows: list[Row] = [
        ([f'{hour:02d}.00-{hour + 1:02d}.00', *_figures(by_hour[hour])], False)
        for hour in hours
    ]
    rows.append((['Total', *_figures(report)], True))
    return workbook(
        'Laba Kotor per Jam',
        long_date(report.day),
        [Column('Jam', 14), *FIGURE_COLUMNS],
        rows,
    )


def _period(start: date, end: date) -> str:
    return f'{long_date(start)} s.d. {long_date(end)}'


def fast_moving(report: FastMoving) -> bytes:
    rows: list[Row] = [
        (
            [
                rank,
                sku_label(row.product_name, row.size, row.color),
                row.code,
                row.category_name,
                row.units_sold,
                rupiah(row.net_sales),
                row.stock,
            ],
            False,
        )
        for rank, row in enumerate(report.rows, start=1)
    ]
    return workbook(
        'Fast Moving',
        _period(report.start, report.end),
        [
            Column('Peringkat', 10),
            Column('Barang', 36),
            Column('Kode', 16),
            Column('Kategori', 18),
            Column('Terjual', 10),
            Column('Penjualan bersih', 16, MONEY),
            Column('Stok', 10),
        ],
        rows,
    )


def abc(report: AbcReport) -> bytes:
    rows: list[Row] = [
        (
            [
                row.abc_class.value,
                sku_label(row.product_name, row.size, row.color),
                row.code,
                row.category_name,
                rupiah(row.net_sales),
                row.share,
                row.running_share,
            ],
            False,
        )
        for row in report.rows
    ]
    for total in report.classes:
        rows.append(
            (
                [
                    f'Kelas {total.abc_class.value}',
                    f'{total.sku_count} SKU',
                    '',
                    '',
                    rupiah(total.net_sales),
                    total.share,
                    '',
                ],
                True,
            )
        )
    rows.append(
        (['Total', '', '', '', rupiah(report.net_sales), '', ''], True)
    )
    return workbook(
        'Kontribusi Omzet',
        _period(report.start, report.end),
        [
            Column('Kelas', 8),
            Column('Barang', 36),
            Column('Kode', 16),
            Column('Kategori', 18),
            Column('Penjualan bersih', 16, MONEY),
            Column('Porsi', 10, PERCENT),
            Column('Kumulatif', 10, PERCENT),
        ],
        rows,
    )
