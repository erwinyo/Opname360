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
    BalanceSheet,
    DailyStock,
    FastMoving,
    HourlySales,
    ProfitAndLoss,
    SalesFigures,
    SalesGroupBy,
    SalesReport,
    SalesRow,
    StatementLine,
    StockFlow,
    VarianceFigures,
    VarianceGroupBy,
    VarianceReport,
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


VARIANCE_TITLES = {
    VarianceGroupBy.sku: 'Barang',
    VarianceGroupBy.reason: 'Alasan',
    VarianceGroupBy.resolution: 'Keputusan',
}


def variances(report: VarianceReport) -> bytes:
    def figures(part: VarianceFigures) -> list[object]:
        return [
            part.line_count,
            part.shortage_quantity,
            rupiah(part.shortage_value),
            part.surplus_quantity,
            rupiah(part.surplus_value),
            rupiah(part.net_value),
        ]

    rows: list[Row] = [
        ([row.label, row.code or '', *figures(row)], False)
        for row in report.rows
    ]
    rows.append((['Total', '', *figures(report.total)], True))
    return workbook(
        'Selisih Opname',
        _period(report.start, report.end),
        [
            Column(VARIANCE_TITLES[report.group_by], 36),
            Column('Kode', 16),
            Column('Baris', 8),
            Column('Kurang', 10),
            Column('Nilai kurang', 16, MONEY),
            Column('Lebih', 10),
            Column('Nilai lebih', 16, MONEY),
            Column('Selisih bersih', 16, MONEY),
        ],
        rows,
    )


def _statement_rows(
    title: str, lines: list[StatementLine], total: Decimal, total_label: str
) -> list[Row]:
    rows: list[Row] = [([title, ''], True)]
    rows += [
        (
            [
                f'    {line.code or ""} {line.name}'.rstrip(),
                rupiah(line.amount),
            ],
            False,
        )
        for line in lines
    ]
    rows.append(([total_label, rupiah(total)], True))
    rows.append((['', ''], False))
    return rows


def profit_and_loss(report: ProfitAndLoss) -> bytes:
    rows: list[Row] = [
        *_statement_rows(
            'Pendapatan usaha',
            report.sales,
            report.net_sales,
            'Penjualan bersih',
        ),
        *_statement_rows(
            'Harga pokok penjualan',
            report.cogs,
            report.total_cogs,
            'Jumlah HPP',
        ),
        (['Laba kotor', rupiah(report.gross_profit)], True),
        (['', ''], False),
        *_statement_rows(
            'Beban', report.expenses, report.total_expenses, 'Jumlah beban'
        ),
        *_statement_rows(
            'Pendapatan lain',
            report.other_income,
            report.total_other_income,
            'Jumlah pendapatan lain',
        ),
        (['Laba bersih', rupiah(report.net_profit)], True),
    ]
    return workbook(
        'Laba Rugi',
        _period(report.start, report.end),
        [Column('Akun', 44), Column('Jumlah', 18, MONEY)],
        rows,
    )


def balance_sheet(report: BalanceSheet) -> bytes:
    """T layout: assets on the left, liabilities and equity on the right."""

    def side(
        groups: list[tuple[str, list[StatementLine], Decimal]],
    ) -> list[tuple[str, object, bool]]:
        cells: list[tuple[str, object, bool]] = []
        for title, lines, total in groups:
            cells.append((title, '', True))
            cells += [
                (
                    f'    {line.code or ""} {line.name}'.rstrip(),
                    rupiah(line.amount),
                    False,
                )
                for line in lines
            ]
            cells.append((f'Jumlah {title.lower()}', rupiah(total), True))
        return cells

    left = side([('Aset', report.assets, report.total_assets)])
    right = side(
        [
            ('Kewajiban', report.liabilities, report.total_liabilities),
            ('Ekuitas', report.equity, report.total_equity),
        ]
    )
    height = max(len(left), len(right))
    blank: tuple[str, object, bool] = ('', '', False)
    left += [blank] * (height - len(left))
    right += [blank] * (height - len(right))
    rows: list[Row] = [
        ([a[0], a[1], b[0], b[1]], a[2] or b[2])
        for a, b in zip(left, right, strict=True)
    ]
    rows.append(
        (
            [
                'Total aset',
                rupiah(report.total_assets),
                'Total kewajiban dan ekuitas',
                rupiah(report.total_liabilities_and_equity),
            ],
            True,
        )
    )
    return workbook(
        'Neraca',
        f'Per {long_date(report.on)}',
        [
            Column('Aset', 36),
            Column('Jumlah', 18, MONEY),
            Column('Kewajiban dan ekuitas', 36),
            Column('Jumlah', 18, MONEY),
        ],
        rows,
    )
