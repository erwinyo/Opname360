from sqlalchemy import Sequence
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from opname360.core.errors import AppError, ConflictError, NotFoundError
from opname360.core.formatting import rupiah, sku_label
from opname360.models import (
    Category,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    CostingMethod,
    Product,
    ProductFilter,
    ProductPage,
    ProductPublic,
    ProductSave,
    Sku,
    SkuOption,
    SkuPriceChange,
    SkuPriceChangePublic,
    SkuSave,
    SubCategory,
    SubCategoryPublic,
    User,
)
from opname360.services import activity_log, costing, stock


METHOD_LABELS = {
    CostingMethod.moving_average: 'Rata-rata',
    CostingMethod.fifo: 'FIFO',
}

# A new SKU's id is taken up front, so a generated code and Barcode can be
# built from it before the row is inserted.
SKU_ID_SEQUENCE = Sequence('sku_id_seq')


def generated_code(sku_id: int) -> str:
    return f'S{sku_id:06d}'


def generated_barcode(sku_id: int) -> str:
    """Eight digits starting with 2: the range kept free for in-store codes."""
    return f'2{sku_id:07d}'


def next_sku_id(session: Session) -> int:
    return session.exec(select(SKU_ID_SEQUENCE.next_value())).one()


def _clean(value: str | None) -> str | None:
    return (value or '').strip() or None


def _required(value: str, what: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise AppError(f'{what} wajib diisi.')
    return cleaned


# Categories


def list_categories(session: Session) -> list[CategoryPublic]:
    counts = _product_counts(session)
    categories = session.exec(
        select(Category).order_by(col(Category.name))
    ).all()
    return [_category_public(category, counts) for category in categories]


def category_public(session: Session, category: Category) -> CategoryPublic:
    return _category_public(category, _product_counts(session))


def get_category(session: Session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise NotFoundError('Kategori tidak ditemukan.')
    return category


def get_sub_category(session: Session, sub_category_id: int) -> SubCategory:
    sub_category = session.get(SubCategory, sub_category_id)
    if sub_category is None:
        raise NotFoundError('Sub-kategori tidak ditemukan.')
    return sub_category


def create_category(
    session: Session, category_in: CategoryCreate, *, actor: User
) -> Category:
    name = _required(category_in.name, 'Nama kategori')
    _check_category_name(session, name)

    category = Category(name=name, costing_method=category_in.costing_method)
    session.add(category)
    session.flush()
    activity_log.record(
        session,
        actor=actor,
        action='category.create',
        summary=(
            f'Menambah kategori {name} '
            f'(HPP {METHOD_LABELS[category.costing_method]}).'
        ),
        entity_type='category',
        entity_id=category.id,
    )
    session.commit()
    return category


def update_category(
    session: Session,
    category: Category,
    category_in: CategoryUpdate,
    *,
    actor: User,
) -> Category:
    changes = []
    if category_in.name is not None:
        name = _required(category_in.name, 'Nama kategori')
        if name != category.name:
            _check_category_name(session, name, exclude=category)
            changes.append(f'nama dari {category.name} menjadi {name}')
            category.name = name
    if changes:
        session.add(category)
        activity_log.record(
            session,
            actor=actor,
            action='category.update',
            summary=f'Mengubah kategori {category.name}: {", ".join(changes)}.',
            entity_type='category',
            entity_id=category.id,
        )
        session.commit()
    return category


def switch_costing_method(
    session: Session,
    category: Category,
    method: CostingMethod,
    *,
    actor: User,
) -> Category:
    """The Owner's switch, from this moment on (slice 6, rules 1-5)."""
    locked = session.get(
        Category, category.id, with_for_update=True, populate_existing=True
    )
    assert locked is not None
    category = locked
    if method == category.costing_method:
        raise ConflictError(
            f'{category.name} sudah memakai HPP {METHOD_LABELS[method]}.'
        )
    before = METHOD_LABELS[category.costing_method]
    value = costing.switch_method(session, category, method)
    activity_log.record(
        session,
        actor=actor,
        action='category.switch_costing_method',
        summary=(
            f'Mengganti metode HPP {category.name} dari {before} ke '
            f'{METHOD_LABELS[method]}; nilai stok saat itu '
            f'{rupiah(round(value))}.'
        ),
        entity_type='category',
        entity_id=category.id,
    )
    session.commit()
    return category


def delete_category(
    session: Session, category: Category, *, actor: User
) -> None:
    has_products = session.exec(
        select(Product.id)
        .join(SubCategory)
        .where(SubCategory.category_id == category.id)
        .limit(1)
    ).first()
    if has_products is not None:
        raise ConflictError(
            f'Kategori {category.name} masih berisi produk. '
            'Pindahkan atau hapus produknya dulu.'
        )
    activity_log.record(
        session,
        actor=actor,
        action='category.delete',
        summary=f'Menghapus kategori {category.name}.',
        entity_type='category',
        entity_id=category.id,
    )
    session.delete(category)
    session.commit()


def create_sub_category(
    session: Session, category: Category, name: str, *, actor: User
) -> SubCategory:
    assert category.id is not None
    name = _required(name, 'Nama sub-kategori')
    _check_sub_category_name(session, category, name)

    sub_category = SubCategory(category_id=category.id, name=name)
    session.add(sub_category)
    session.flush()
    activity_log.record(
        session,
        actor=actor,
        action='sub_category.create',
        summary=f'Menambah sub-kategori {name} di {category.name}.',
        entity_type='sub_category',
        entity_id=sub_category.id,
    )
    session.commit()
    return sub_category


def rename_sub_category(
    session: Session, sub_category: SubCategory, name: str, *, actor: User
) -> SubCategory:
    name = _required(name, 'Nama sub-kategori')
    if name != sub_category.name:
        _check_sub_category_name(
            session, sub_category.category, name, exclude=sub_category
        )
        activity_log.record(
            session,
            actor=actor,
            action='sub_category.update',
            summary=(
                f'Mengubah nama sub-kategori {sub_category.name} '
                f'menjadi {name}.'
            ),
            entity_type='sub_category',
            entity_id=sub_category.id,
        )
        sub_category.name = name
        session.add(sub_category)
        session.commit()
    return sub_category


def delete_sub_category(
    session: Session, sub_category: SubCategory, *, actor: User
) -> None:
    has_products = session.exec(
        select(Product.id)
        .where(Product.sub_category_id == sub_category.id)
        .limit(1)
    ).first()
    if has_products is not None:
        raise ConflictError(
            f'Sub-kategori {sub_category.name} masih berisi produk. '
            'Pindahkan atau hapus produknya dulu.'
        )
    activity_log.record(
        session,
        actor=actor,
        action='sub_category.delete',
        summary=f'Menghapus sub-kategori {sub_category.name}.',
        entity_type='sub_category',
        entity_id=sub_category.id,
    )
    session.delete(sub_category)
    session.commit()


def _product_counts(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(Product.sub_category_id, func.count()).group_by(
            col(Product.sub_category_id)
        )
    ).all()
    return dict(rows)


def _category_public(
    category: Category, counts: dict[int, int]
) -> CategoryPublic:
    return CategoryPublic.model_validate(
        category,
        update={
            'sub_categories': [
                SubCategoryPublic.model_validate(
                    sub, update={'product_count': counts.get(sub.id or 0, 0)}
                )
                for sub in category.sub_categories
            ]
        },
    )


def _check_category_name(
    session: Session, name: str, *, exclude: Category | None = None
) -> None:
    query = select(Category.id).where(
        func.lower(Category.name) == name.lower()
    )
    if exclude is not None:
        query = query.where(Category.id != exclude.id)
    if session.exec(query).first() is not None:
        raise ConflictError(f'Kategori "{name}" sudah ada.')


def _check_sub_category_name(
    session: Session,
    category: Category,
    name: str,
    *,
    exclude: SubCategory | None = None,
) -> None:
    query = select(SubCategory.id).where(
        SubCategory.category_id == category.id,
        func.lower(SubCategory.name) == name.lower(),
    )
    if exclude is not None:
        query = query.where(SubCategory.id != exclude.id)
    if session.exec(query).first() is not None:
        raise ConflictError(
            f'Sub-kategori "{name}" sudah ada di {category.name}.'
        )


# Products and SKUs


def list_products(session: Session, filters: ProductFilter) -> ProductPage:
    query = select(Product).join(SubCategory)
    if filters.sub_category_id is not None:
        query = query.where(Product.sub_category_id == filters.sub_category_id)
    if filters.category_id is not None:
        query = query.where(SubCategory.category_id == filters.category_id)
    search = _clean(filters.search)
    if search:
        sku_matches = (
            select(Sku.id)
            .where(
                Sku.product_id == Product.id,
                or_(
                    col(Sku.code).icontains(search, autoescape=True),
                    col(Sku.barcode).icontains(search, autoescape=True),
                ),
            )
            .exists()
        )
        query = query.where(
            or_(
                col(Product.name).icontains(search, autoescape=True),
                sku_matches,
            )
        )

    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    products = session.exec(
        query.options(
            selectinload(Product.skus),  # ty: ignore[invalid-argument-type]
            selectinload(Product.sub_category).selectinload(  # ty: ignore[invalid-argument-type]
                SubCategory.category  # ty: ignore[invalid-argument-type]
            ),
        )
        .order_by(col(Product.name))
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return ProductPage(
        items=[product_public(product) for product in products], total=total
    )


def get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise NotFoundError('Produk tidak ditemukan.')
    return product


def get_sku(session: Session, sku_id: int) -> Sku:
    sku = session.get(Sku, sku_id)
    if sku is None:
        raise NotFoundError('SKU tidak ditemukan.')
    return sku


def product_public(product: Product) -> ProductPublic:
    sub_category = product.sub_category
    return ProductPublic.model_validate(
        product,
        update={
            'sub_category_name': sub_category.name,
            'category_id': sub_category.category_id,
            'category_name': sub_category.category.name,
        },
    )


def create_product(
    session: Session, product_in: ProductSave, *, actor: User
) -> Product:
    return _save_product(session, None, product_in, actor=actor)


def update_product(
    session: Session, product: Product, product_in: ProductSave, *, actor: User
) -> Product:
    return _save_product(session, product, product_in, actor=actor)


def delete_product(session: Session, product: Product, *, actor: User) -> None:
    if stock.has_movements(session, _sku_ids(session, product=product)):
        raise ConflictError(
            f'{product.name} sudah punya riwayat stok dan tidak bisa dihapus. '
            'Nonaktifkan SKU-nya saja.'
        )
    activity_log.record(
        session,
        actor=actor,
        action='product.delete',
        summary=f'Menghapus produk {product.name}.',
        entity_type='product',
        entity_id=product.id,
    )
    session.delete(product)
    session.commit()


def list_price_changes(
    session: Session, sku: Sku
) -> list[SkuPriceChangePublic]:
    rows = session.exec(
        select(SkuPriceChange, User.full_name)
        .join(User, isouter=True)
        .where(SkuPriceChange.sku_id == sku.id)
        .order_by(col(SkuPriceChange.id).desc())
    ).all()
    return [
        SkuPriceChangePublic.model_validate(
            change, update={'changed_by_name': name}
        )
        for change, name in rows
    ]


def _save_product(
    session: Session,
    product: Product | None,
    product_in: ProductSave,
    *,
    actor: User,
) -> Product:
    """Create or update a Product so its SKUs match `product_in` exactly."""
    name = _required(product_in.name, 'Nama produk')
    sub_category = get_sub_category(session, product_in.sub_category_id)
    assert sub_category.id is not None
    _check_product_name(session, sub_category, name, exclude=product)
    _check_rows(product_in.skus)

    existing = {sku.id: sku for sku in product.skus} if product else {}
    if any(
        row.id is not None and row.id not in existing
        for row in product_in.skus
    ):
        raise NotFoundError('SKU yang diubah bukan milik produk ini.')

    # Settle every SKU's id, code and Barcode before anything is written, so
    # a clash with another Product is refused with a clear message.
    rows = []
    for row in product_in.skus:
        sku_id = row.id or next_sku_id(session)
        code = _clean(row.code) or generated_code(sku_id)
        barcode = _clean(row.barcode) or generated_barcode(sku_id)
        rows.append((row, sku_id, code, barcode))
    _check_codes_are_free(
        session,
        codes=[code for _, _, code, _ in rows],
        barcodes=[barcode for _, _, _, barcode in rows],
        own=product,
    )

    is_new = product is None
    if product is None:
        product = Product(name=name, sub_category_id=sub_category.id)
    else:
        product.name = name
        product.sub_category_id = sub_category.id
    session.add(product)
    try:
        # Removed SKUs go first, freeing their code and Barcode for reuse.
        kept = {row.id for row in product_in.skus}
        removed = [
            sku for sku_id, sku in existing.items() if sku_id not in kept
        ]
        for sku in removed:
            if stock.has_movements(session, [sku.id or 0]):
                label = sku_label(product.name, sku.size, sku.color)
                session.rollback()
                raise ConflictError(
                    f'{label} sudah punya riwayat stok dan tidak bisa '
                    'dihapus. Nonaktifkan saja.'
                )
            session.delete(sku)
        session.flush()
        assert product.id is not None

        for row, sku_id, code, barcode in rows:
            sku = existing.get(sku_id)
            if sku is None:
                sku = Sku(
                    id=sku_id,
                    product_id=product.id,
                    code=code,
                    barcode=barcode,
                    selling_price=row.selling_price,
                )
                _record_price(session, product, sku, None, row, actor=actor)
            elif row.selling_price != sku.selling_price:
                _record_price(
                    session, product, sku, sku.selling_price, row, actor=actor
                )
            sku.code = code
            sku.barcode = barcode
            sku.size = _clean(row.size)
            sku.color = _clean(row.color)
            sku.stock_unit = row.stock_unit.strip()
            sku.purchase_pack_name = _clean(row.purchase_pack_name)
            sku.purchase_pack_size = row.purchase_pack_size
            sku.selling_price = row.selling_price
            sku.is_active = row.is_active
            session.add(sku)
        session.flush()
    except IntegrityError as error:
        # Two SKUs of this Product trading codes in one save, or a race.
        session.rollback()
        raise ConflictError(
            'Kode atau barcode bentrok dengan SKU lain. Periksa lalu simpan lagi.'
        ) from error

    activity_log.record(
        session,
        actor=actor,
        action='product.create' if is_new else 'product.update',
        summary=(
            f'{"Menambah" if is_new else "Mengubah"} produk {name} '
            f'({len(rows)} SKU).'
        ),
        entity_type='product',
        entity_id=product.id,
    )
    session.commit()
    return product


def _record_price(
    session: Session,
    product: Product,
    sku: Sku,
    old_price: int | None,
    row: SkuSave,
    *,
    actor: User,
) -> None:
    assert sku.id is not None
    session.add(
        SkuPriceChange(
            sku_id=sku.id,
            old_price=old_price,
            new_price=row.selling_price,
            changed_by=actor.id,
        )
    )
    if old_price is None:
        return
    activity_log.record(
        session,
        actor=actor,
        action='sku.price_change',
        summary=(
            f'Harga jual {sku_label(product.name, sku.size, sku.color)} '
            f'berubah dari {rupiah(old_price)} '
            f'menjadi {rupiah(row.selling_price)}.'
        ),
        entity_type='sku',
        entity_id=sku.id,
    )


def _check_product_name(
    session: Session,
    sub_category: SubCategory,
    name: str,
    *,
    exclude: Product | None,
) -> None:
    query = select(Product.id).where(
        Product.sub_category_id == sub_category.id,
        func.lower(Product.name) == name.lower(),
    )
    if exclude is not None:
        query = query.where(Product.id != exclude.id)
    if session.exec(query).first() is not None:
        raise ConflictError(
            f'Produk "{name}" sudah ada di {sub_category.name}.'
        )


def _check_rows(rows: list[SkuSave]) -> None:
    """Within one Product: no repeated variant, code or Barcode."""
    variants = set()
    codes = set()
    barcodes = set()
    for row in rows:
        size, color = _clean(row.size), _clean(row.color)
        variant = ((size or '').lower(), (color or '').lower())
        if variant in variants:
            described = ', '.join(part for part in (size, color) if part)
            raise ConflictError(
                f'Varian {described} muncul dua kali.'
                if described
                else 'Hanya satu SKU yang boleh tanpa ukuran dan warna.'
            )
        variants.add(variant)

        code = _clean(row.code)
        if code and code.lower() in codes:
            raise ConflictError(f'Kode {code} muncul dua kali.')
        if code:
            codes.add(code.lower())

        barcode = _clean(row.barcode)
        if barcode and barcode in barcodes:
            raise ConflictError(f'Barcode {barcode} muncul dua kali.')
        if barcode:
            barcodes.add(barcode)


def _check_codes_are_free(
    session: Session,
    *,
    codes: list[str],
    barcodes: list[str],
    own: Product | None,
) -> None:
    """Against every other Product: a code or Barcode belongs to one SKU."""
    query = select(Sku).where(
        or_(
            col(Sku.barcode).in_(barcodes),
            func.lower(Sku.code).in_([code.lower() for code in codes]),
        )
    )
    if own is not None:
        query = query.where(Sku.product_id != own.id)
    clash = session.exec(query.limit(1)).first()
    if clash is None:
        return
    owner = sku_label(clash.product.name, clash.size, clash.color)
    if clash.barcode in barcodes:
        raise ConflictError(
            f'Barcode {clash.barcode} sudah dipakai oleh {owner}.'
        )
    raise ConflictError(f'Kode {clash.code} sudah dipakai oleh {owner}.')


def search_skus(
    session: Session, query: str, *, limit: int
) -> list[SkuOption]:
    """Active SKUs for a scan or a typed search, exact Barcode or code first."""
    query = query.strip()
    if not query:
        return []
    exact = session.exec(
        select(Sku).where(
            col(Sku.is_active).is_(True),
            or_(Sku.barcode == query, func.lower(Sku.code) == query.lower()),
        )
    ).all()
    found = list(exact)
    if not found:
        found = list(
            session.exec(
                select(Sku)
                .join(Product)
                .where(
                    col(Sku.is_active).is_(True),
                    or_(
                        col(Product.name).icontains(query, autoescape=True),
                        col(Sku.code).icontains(query, autoescape=True),
                        col(Sku.barcode).icontains(query, autoescape=True),
                    ),
                )
                .order_by(col(Product.name), col(Sku.id))
                .limit(limit)
            ).all()
        )
    return [
        SkuOption.model_validate(
            sku, update={'product_name': sku.product.name}
        )
        for sku in found
    ]


def _sku_ids(
    session: Session,
    *,
    category: Category | None = None,
    product: Product | None = None,
) -> list[int]:
    query = select(Sku.id).join(Product).join(SubCategory)
    if category is not None:
        query = query.where(SubCategory.category_id == category.id)
    if product is not None:
        query = query.where(Sku.product_id == product.id)
    return [
        sku_id for sku_id in session.exec(query).all() if sku_id is not None
    ]


def skus_by_id(session: Session, sku_ids: list[int]) -> list[SkuOption]:
    """The given SKUs, in the order asked for; unknown ids are skipped."""
    found = {
        sku.id: sku
        for sku in session.exec(
            select(Sku).where(col(Sku.id).in_(sku_ids))
        ).all()
    }
    return [
        SkuOption.model_validate(
            found[sku_id], update={'product_name': found[sku_id].product.name}
        )
        for sku_id in dict.fromkeys(sku_ids)
        if sku_id in found
    ]
