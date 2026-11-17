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
from opname360.models import DailyStock, StockFlow


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
