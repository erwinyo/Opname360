"""Import the catalogue from an Excel file: everything, or nothing at all.

One row is one SKU. Rows with the same Category, Sub-category and product
name become one Product.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import BadZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError
from opname360.core.formatting import sku_label
from opname360.models import (
    Category,
    CostingMethod,
    ImportPreview,
    ImportProblem,
    ImportResult,
    Product,
    Sku,
    SkuPriceChange,
    SubCategory,
    User,
)
from opname360.services import activity_log, catalogue


MAX_ROWS = 10_000
ANGLE = '\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}'


@dataclass(frozen=True)
class Column:
    title: str
    required: bool
    max_length: int | None
    help: str


COLUMNS = {
    'category': Column('Kategori', True, 100, 'Misalnya Seragam, ATK.'),
    'sub_category': Column(
        'Sub-kategori', True, 100, 'Misalnya Kemeja, Topi, Pulpen.'
    ),
    'product': Column(
        'Nama produk',
        True,
        200,
        'Tanpa ukuran atau warna. Baris dengan kategori, sub-kategori dan '
        'nama yang sama menjadi satu produk.',
    ),
    'size': Column('Ukuran', False, 50, 'Boleh kosong.'),
    'color': Column('Warna', False, 50, 'Boleh kosong.'),
    'stock_unit': Column(
        'Satuan', False, 20, 'Satuan stok dan jual. Kosong berarti pcs.'
    ),
    'selling_price': Column(
        'Harga jual', True, None, 'Rupiah, tanpa desimal.'
    ),
    'barcode': Column(
        'Barcode',
        False,
        64,
        'Barcode pabrik bila ada. Kosong berarti dibuatkan otomatis.',
    ),
    'code': Column(
        'Kode', False, 50, 'Kode toko. Kosong berarti dibuatkan otomatis.'
    ),
    'pack_name': Column(
        'Kemasan beli', False, 20, 'Misalnya box. Isi bersama Isi kemasan.'
    ),
    'pack_size': Column(
        'Isi kemasan', False, None, 'Berapa satuan dalam satu kemasan beli.'
    ),
    'latest_cost': Column(
        'Harga beli terakhir',
        False,
        None,
        'Per satuan. Dipakai sebagai harga pokok awal saat opname awal.',
    ),
}


@dataclass
class Row:
    number: int
    category: str = ''
    sub_category: str = ''
    product: str = ''
    size: str | None = None
    color: str | None = None
    stock_unit: str = 'pcs'
    selling_price: int = 0
    barcode: str | None = None
    code: str | None = None
    pack_name: str | None = None
    pack_size: Decimal | None = None
    latest_cost: Decimal | None = None

    @property
    def product_key(self) -> tuple[str, str, str]:
        return (
            self.category.lower(),
            self.sub_category.lower(),
            self.product.lower(),
        )


@dataclass
class Plan:
    rows: list[Row] = field(default_factory=list)
    problems: list[ImportProblem] = field(default_factory=list)
    categories: dict[str, Category] = field(default_factory=dict)
    sub_categories: dict[tuple[str, str], SubCategory] = field(
        default_factory=dict
    )
    new_categories: list[str] = field(default_factory=list)
    new_sub_categories: list[tuple[str, str]] = field(default_factory=list)

    def problem(
        self, message: str, row: int | None = None, column: str | None = None
    ) -> None:
        title = COLUMNS[column].title if column in COLUMNS else column
        self.problems.append(
            ImportProblem(row=row, column=title, message=message)
        )


def template() -> bytes:
    """An empty import file with the columns and a sheet explaining them."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = 'Produk'
    sheet.append([column.title for column in COLUMNS.values()])
    for index, (key, column) in enumerate(COLUMNS.items(), start=1):
        cell = sheet.cell(row=1, column=index)
        cell.font = Font(bold=True)
        letter = cell.column_letter
        sheet.column_dimensions[letter].width = max(len(column.title) + 4, 14)
        if key in ('barcode', 'code'):
            # As text, so Excel keeps leading zeros and long numbers.
            sheet.column_dimensions[letter].number_format = '@'
    sheet.freeze_panes = 'A2'

    guide = workbook.create_sheet('Petunjuk')
    guide.append(['Kolom', 'Wajib', 'Keterangan'])
    for cell in guide[1]:
        cell.font = Font(bold=True)
    for column in COLUMNS.values():
        guide.append(
            [column.title, 'Ya' if column.required else '', column.help]
        )
    guide.column_dimensions['A'].width = 22
    guide.column_dimensions['C'].width = 90

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def preview(session: Session, data: bytes) -> ImportPreview:
    plan = _plan(session, data)
    return ImportPreview(
        product_count=len({row.product_key for row in plan.rows}),
        sku_count=len(plan.rows),
        new_categories=plan.new_categories,
        new_sub_categories=[
            f'{category} {ANGLE} {sub}'
            for category, sub in plan.new_sub_categories
        ],
        problems=plan.problems,
    )


def run(
    session: Session, data: bytes, *, filename: str, actor: User
) -> ImportResult:
    plan = _plan(session, data)
    if plan.problems:
        raise ConflictError(
            f'File masih punya {len(plan.problems)} masalah. '
            'Perbaiki dulu sesuai pratinjau.'
        )
    if not plan.rows:
        raise ConflictError('File tidak berisi produk.')

    try:
        for name in plan.new_categories:
            category = Category(
                name=name, costing_method=CostingMethod.moving_average
            )
            session.add(category)
            plan.categories[name.lower()] = category
        session.flush()
        for category_name, name in plan.new_sub_categories:
            category = plan.categories[category_name.lower()]
            assert category.id is not None
            sub_category = SubCategory(category_id=category.id, name=name)
            session.add(sub_category)
            plan.sub_categories[(category_name.lower(), name.lower())] = (
                sub_category
            )
        session.flush()

        products: dict[tuple[str, str, str], Product] = {}
        for row in plan.rows:
            product = products.get(row.product_key)
            if product is None:
                sub_category = plan.sub_categories[row.product_key[:2]]
                assert sub_category.id is not None
                product = Product(
                    name=row.product, sub_category_id=sub_category.id
                )
                session.add(product)
                session.flush()
                products[row.product_key] = product
            assert product.id is not None
            sku_id = catalogue.next_sku_id(session)
            session.add(
                Sku(
                    id=sku_id,
                    product_id=product.id,
                    code=row.code or catalogue.generated_code(sku_id),
                    barcode=row.barcode or catalogue.generated_barcode(sku_id),
                    size=row.size,
                    color=row.color,
                    stock_unit=row.stock_unit,
                    purchase_pack_name=row.pack_name,
                    purchase_pack_size=row.pack_size,
                    selling_price=row.selling_price,
                    latest_unit_cost=row.latest_cost,
                )
            )
            session.add(
                SkuPriceChange(
                    sku_id=sku_id,
                    new_price=row.selling_price,
                    changed_by=actor.id,
                )
            )
        session.flush()
    except IntegrityError as error:
        # Someone saved a clashing code or Barcode while this ran.
        session.rollback()
        raise ConflictError(
            'Data katalog berubah saat impor berjalan. Coba pratinjau lagi.'
        ) from error

    activity_log.record(
        session,
        actor=actor,
        action='product.import',
        summary=(
            f'Mengimpor {len(products)} produk ({len(plan.rows)} SKU) '
            f'dari {filename}.'
        ),
    )
    session.commit()
    return ImportResult(
        product_count=len(products),
        sku_count=len(plan.rows),
        category_count=len(plan.new_categories),
        sub_category_count=len(plan.new_sub_categories),
    )


def _plan(session: Session, data: bytes) -> Plan:
    """Read the file and check every row against itself and the catalogue."""
    plan = Plan()
    if not _read(plan, data):
        return plan
    _check_variants(plan)
    _check_codes(session, plan)
    _match_catalogue(session, plan)
    plan.problems.sort(key=lambda problem: problem.row or 0)
    return plan


def _read(plan: Plan, data: bytes) -> bool:
    """Fill `plan.rows`; False when the file itself can't be used."""
    try:
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except (BadZipFile, KeyError, OSError, ValueError):
        plan.problem('File ini bukan file Excel (.xlsx) yang bisa dibaca.')
        return False
    sheet = workbook.worksheets[0]
    lines = sheet.iter_rows(values_only=True)
    header = next(lines, None) or ()
    positions = {
        str(title).strip().lower(): index
        for index, title in enumerate(header)
        if title is not None
    }
    columns: dict[str, int] = {}
    for key, column in COLUMNS.items():
        position = positions.get(column.title.lower())
        if position is not None:
            columns[key] = position
        elif column.required:
            plan.problem(
                'Kolom ini tidak ada di baris pertama. Pakai template.',
                row=1,
                column=key,
            )
    if plan.problems:
        return False

    for number, values in enumerate(lines, start=2):
        if all(_text(value) is None for value in values):
            continue
        if len(plan.rows) == MAX_ROWS:
            plan.problem(f'File berisi lebih dari {MAX_ROWS} baris produk.')
            return False
        row = Row(number=number)
        for key, position in columns.items():
            value = values[position] if position < len(values) else None
            _set(plan, row, key, value)
        plan.rows.append(row)
    workbook.close()
    return True


def _set(plan: Plan, row: Row, key: str, value: object) -> None:
    column = COLUMNS[key]
    if key in ('selling_price', 'pack_size', 'latest_cost'):
        number = _number(value)
        if number is None:
            if _text(value) is not None:
                plan.problem('Bukan angka.', row.number, key)
            elif column.required:
                plan.problem('Wajib diisi.', row.number, key)
            return
        if number < 0:
            plan.problem('Tidak boleh minus.', row.number, key)
            return
        if key == 'pack_size' and number == 0:
            plan.problem('Harus lebih dari 0.', row.number, key)
            return
        if key == 'selling_price':
            row.selling_price = int(number.to_integral_value())
        else:
            setattr(row, key, number)
        return

    text = _text(value)
    if text is None:
        if column.required:
            plan.problem('Wajib diisi.', row.number, key)
        return
    if column.max_length and len(text) > column.max_length:
        plan.problem(
            f'Terlalu panjang (paling banyak {column.max_length} karakter).',
            row.number,
            key,
        )
        return
    setattr(row, key, text)


def _check_variants(plan: Plan) -> None:
    """Per Product: one row per variant, and a pack needs name and size."""
    seen: dict[tuple, int] = {}
    for row in plan.rows:
        if (row.pack_name is None) != (row.pack_size is None):
            plan.problem(
                'Isi Kemasan beli dan Isi kemasan bersama, atau kosongkan '
                'keduanya.',
                row.number,
                'pack_name',
            )
        if not all(row.product_key):
            continue
        variant = (
            row.product_key,
            (row.size or '').lower(),
            (row.color or '').lower(),
        )
        if variant in seen:
            plan.problem(
                f'Ukuran dan warna yang sama sudah ada di baris '
                f'{seen[variant]} untuk produk ini.',
                row.number,
                'size',
            )
        else:
            seen[variant] = row.number


def _check_codes(session: Session, plan: Plan) -> None:
    """A Barcode and a code each belong to one SKU, in the file and beyond."""
    for key, normalise in (
        ('barcode', lambda value: value),
        ('code', str.lower),
    ):
        first_row: dict[str, int] = {}
        for row in plan.rows:
            value = getattr(row, key)
            if value is None:
                continue
            if normalise(value) in first_row:
                plan.problem(
                    f'{value} sudah dipakai di baris '
                    f'{first_row[normalise(value)]}.',
                    row.number,
                    key,
                )
            else:
                first_row[normalise(value)] = row.number

    barcodes = [row.barcode for row in plan.rows if row.barcode]
    codes = [row.code.lower() for row in plan.rows if row.code]
    taken = _chunked(
        lambda chunk: session.exec(
            select(Sku).where(col(Sku.barcode).in_(chunk))
        ).all(),
        barcodes,
    )
    taken_codes = _chunked(
        lambda chunk: session.exec(
            select(Sku).where(func.lower(Sku.code).in_(chunk))
        ).all(),
        codes,
    )
    by_barcode = {sku.barcode: sku for sku in taken}
    by_code = {sku.code.lower(): sku for sku in taken_codes}
    for row in plan.rows:
        for key, value, owner in (
            ('barcode', row.barcode, by_barcode.get(row.barcode or '')),
            ('code', row.code, by_code.get((row.code or '').lower())),
        ):
            if value and owner is not None:
                label = sku_label(owner.product.name, owner.size, owner.color)
                plan.problem(
                    f'{value} sudah dipakai oleh {label}.', row.number, key
                )


def _match_catalogue(session: Session, plan: Plan) -> None:
    """Find existing Categories and Sub-categories; refuse existing Products."""
    for category in session.exec(select(Category)).all():
        plan.categories[category.name.lower()] = category
        for sub_category in category.sub_categories:
            plan.sub_categories[
                (category.name.lower(), sub_category.name.lower())
            ] = sub_category

    new_categories: set[str] = set()
    new_sub_categories: set[tuple[str, str]] = set()
    reported = set()
    for row in plan.rows:
        if not all(row.product_key):
            continue
        category_key = row.category.lower()
        sub_key = (category_key, row.sub_category.lower())
        if (
            category_key not in plan.categories
            and category_key not in new_categories
        ):
            new_categories.add(category_key)
            plan.new_categories.append(row.category)
        if (
            sub_key not in plan.sub_categories
            and sub_key not in new_sub_categories
        ):
            new_sub_categories.add(sub_key)
            plan.new_sub_categories.append((row.category, row.sub_category))

        sub_category = plan.sub_categories.get(sub_key)
        if sub_category is None or row.product_key in reported:
            continue
        exists = session.exec(
            select(Product.id).where(
                Product.sub_category_id == sub_category.id,
                func.lower(Product.name) == row.product.lower(),
            )
        ).first()
        if exists is not None:
            reported.add(row.product_key)
            plan.problem(
                f'Produk {row.product} sudah ada di {row.sub_category}. '
                'Ubah lewat menu Produk.',
                row.number,
                'product',
            )


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        # Excel stores a Barcode typed as a number as a float.
        value = int(value)
    text = str(value).strip()
    return text or None


def _number(value: object) -> Decimal | None:
    """A number as Excel holds it, or as written in Indonesia: Rp 1.250,5."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return Decimal(str(value))
    text = _text(value)
    if text is None:
        return None
    cleaned = (
        text.lower()
        .removeprefix('rp')
        .strip()
        .replace('.', '')
        .replace(',', '.')
    )
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _chunked[T](
    fetch: Callable[[list[str]], Iterable[T]], values: list[str]
) -> Iterable[T]:
    """Run an IN query in slices, so a big file doesn't hit parameter limits."""
    for start in range(0, len(values), 1000):
        yield from fetch(values[start : start + 1000])
