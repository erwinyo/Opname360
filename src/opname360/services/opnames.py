"""Stock Opname: open a session, count blind, review, approve.

The rules are in docs/plan/slice-2-stock-opname.md; the reason the shop stays
open while counting is ADR 0004.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import and_
from sqlmodel import Session, col, func, or_, select

from opname360.core.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from opname360.core.formatting import ANGLE, sku_label
from opname360.models import (
    Category,
    CountCreate,
    CountEntry,
    CountSheet,
    CountSkuOption,
    CountingSummary,
    EmployeeCharge,
    LineResolutionSave,
    LineShow,
    Location,
    MovementReason,
    MyCountEntry,
    OpnameChecker,
    OpnameFilter,
    OpnameLine,
    OpnameLineFilter,
    OpnameLinePage,
    OpnameLinePublic,
    OpnameOpen,
    OpnamePage,
    OpnamePublic,
    OpnameScope,
    OpnameStatus,
    OpnameSummary,
    Product,
    Resolution,
    Role,
    Sku,
    StaffOption,
    StockBalance,
    StockMovement,
    StockOpname,
    SubCategory,
    UnknownBarcode,
    UnknownBarcodePublic,
    User,
)
from opname360.models._types import utc_now
from opname360.services import (
    activity_log,
    costing,
    documents,
    employee_charges,
    stock,
)


PREFIX = 'SO'  # Stok Opname
DOCUMENT_TYPE = 'stock_opname'
UNFINISHED = (OpnameStatus.counting, OpnameStatus.review)
ZERO = Decimal(0)
MY_ENTRIES_SHOWN = 200


# Opening


def list_staff(session: Session) -> list[StaffOption]:
    """Active users, to pick Checkers and the employee of a charge."""
    users = session.exec(
        select(User)
        .where(col(User.is_active).is_(True))
        .order_by(col(User.full_name))
    ).all()
    return [StaffOption.model_validate(user) for user in users]


def open_opname(
    session: Session, opname_in: OpnameOpen, *, actor: User
) -> StockOpname:
    location_id = stock.resolve_location(session, opname_in.location_id)
    # One opening at a time per Location, so two sessions can't both claim
    # the same SKU (rule 2).
    session.get(Location, location_id, with_for_update=True)

    checkers = _checkers(session, opname_in.checker_ids)
    scope = opname_in.scope
    if opname_in.is_opening:
        scope = OpnameScope.everything
        if _location_has_movements(session, location_id):
            raise ConflictError(
                'Opname awal hanya bisa dibuka sebelum ada mutasi stok di '
                'lokasi ini.'
            )
    sku_ids, scope_label = _scope(session, scope, opname_in, location_id)
    if not sku_ids:
        raise ConflictError('Tidak ada SKU dalam cakupan ini.')

    busy = session.exec(
        select(StockOpname.number, func.count())
        .join(OpnameLine)
        .where(
            StockOpname.location_id == location_id,
            col(StockOpname.status).in_(UNFINISHED),
            col(OpnameLine.sku_id).in_(sku_ids),
        )
        .group_by(col(StockOpname.number))
    ).all()
    if busy:
        sessions = ', '.join(f'{number} ({n} SKU)' for number, n in busy)
        raise ConflictError(
            f'Sebagian SKU masih dihitung di opname lain: {sessions}. '
            'Selesaikan atau batalkan opname itu dulu.'
        )

    opname = StockOpname(
        number=documents.next_number(session, PREFIX),
        location_id=location_id,
        scope=scope,
        scope_label=scope_label,
        is_opening=opname_in.is_opening,
        note=(opname_in.note or '').strip() or None,
        opened_by=actor.id,
    )
    session.add(opname)
    session.flush()
    assert opname.id is not None
    # The import's "last purchase cost" is the opening cost to start from.
    opening_costs = (
        dict(
            session.exec(
                select(col(Sku.id), col(Sku.latest_unit_cost)).where(
                    col(Sku.id).in_(sku_ids)
                )
            ).all()
        )
        if opname.is_opening
        else {}
    )
    for sku_id in sorted(sku_ids):
        session.add(
            OpnameLine(
                opname_id=opname.id,
                sku_id=sku_id,
                unit_cost=opening_costs.get(sku_id),
            )
        )
    for user in checkers:
        assert user.id is not None
        session.add(OpnameChecker(opname_id=opname.id, user_id=user.id))

    kind = 'opname awal' if opname.is_opening else 'stok opname'
    activity_log.record(
        session,
        actor=actor,
        action='stock_opname.open',
        summary=(
            f'Membuka {kind} {opname.number}: {scope_label}, '
            f'{len(sku_ids)} SKU, checker '
            f'{", ".join(user.full_name for user in checkers)}.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=opname.id,
    )
    session.commit()
    return opname


def opening_allowed(session: Session, location_id: int | None) -> bool:
    """Whether an Opening Opname can still be opened here (rule 18)."""
    location_id = stock.resolve_location(session, location_id)
    return not _location_has_movements(session, location_id)


def _checkers(session: Session, user_ids: list[int]) -> list[User]:
    users = session.exec(
        select(User).where(col(User.id).in_(set(user_ids)))
    ).all()
    if len(users) != len(set(user_ids)):
        raise NotFoundError('Checker tidak ditemukan.')
    inactive = [user.full_name for user in users if not user.is_active]
    if inactive:
        raise ConflictError(
            f'Pengguna nonaktif tidak bisa jadi checker: {", ".join(inactive)}.'
        )
    return sorted(users, key=lambda user: user.full_name)


def _location_has_movements(session: Session, location_id: int) -> bool:
    found = session.exec(
        select(StockMovement.id)
        .where(StockMovement.location_id == location_id)
        .limit(1)
    ).first()
    return found is not None


def _scope(
    session: Session,
    scope: OpnameScope,
    opname_in: OpnameOpen,
    location_id: int,
) -> tuple[list[int], str]:
    """The SKUs in Scope and the Scope in words.

    Every active SKU, plus inactive ones that still have stock here (rule 1).
    """
    query = (
        select(Sku.id)
        .join(Product, col(Sku.product_id) == Product.id)
        .join(SubCategory, col(Product.sub_category_id) == SubCategory.id)
        .join(
            StockBalance,
            and_(
                col(StockBalance.sku_id) == Sku.id,
                col(StockBalance.location_id) == location_id,
            ),
            isouter=True,
        )
        .where(
            or_(
                col(Sku.is_active).is_(True),
                func.coalesce(StockBalance.quantity, 0) != 0,
            )
        )
    )
    if scope == OpnameScope.everything:
        label = 'Semua SKU'
    elif scope == OpnameScope.categories:
        ids = _chosen(opname_in.category_ids, 'kategori')
        names = session.exec(
            select(Category.name)
            .where(col(Category.id).in_(ids))
            .order_by(col(Category.name))
        ).all()
        if len(names) != len(ids):
            raise NotFoundError('Kategori tidak ditemukan.')
        query = query.where(col(SubCategory.category_id).in_(ids))
        label = ', '.join(names)
    elif scope == OpnameScope.sub_categories:
        ids = _chosen(opname_in.sub_category_ids, 'sub-kategori')
        rows = session.exec(
            select(Category.name, SubCategory.name)
            .join(SubCategory)
            .where(col(SubCategory.id).in_(ids))
            .order_by(col(Category.name), col(SubCategory.name))
        ).all()
        if len(rows) != len(ids):
            raise NotFoundError('Sub-kategori tidak ditemukan.')
        query = query.where(col(Product.sub_category_id).in_(ids))
        label = ', '.join(
            f'{category} {ANGLE} {sub}' for category, sub in rows
        )
    else:
        ids = _chosen(opname_in.sku_ids, 'SKU')
        found = session.exec(
            select(func.count()).select_from(Sku).where(col(Sku.id).in_(ids))
        ).one()
        if found != len(ids):
            raise NotFoundError('SKU tidak ditemukan.')
        query = query.where(col(Sku.id).in_(ids))
        label = f'{len(ids)} SKU pilihan'
    if len(label) > 300:
        label = label[:299] + '…'
    return list(session.exec(query).all()), label


def _chosen(ids: list[int], what: str) -> list[int]:
    if not ids:
        raise AppError(f'Pilih minimal satu {what}.')
    return sorted(set(ids))


# Reading


def get_opname(session: Session, opname_id: int) -> StockOpname:
    opname = session.get(StockOpname, opname_id)
    if opname is None:
        raise NotFoundError('Stok opname tidak ditemukan.')
    return opname


def list_opnames(session: Session, filters: OpnameFilter) -> OpnamePage:
    query = select(StockOpname, Location.name).join(Location)
    if filters.status is not None:
        query = query.where(StockOpname.status == filters.status)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    rows = session.exec(
        query.order_by(col(StockOpname.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    counts = _line_counts(session, [opname.id for opname, _ in rows])
    return OpnamePage(
        items=[
            OpnameSummary.model_validate(
                opname,
                update={
                    'location_name': location_name,
                    'opened_by_name': documents.user_name(
                        session, opname.opened_by
                    ),
                    'line_count': counts.get(opname.id, (0, 0))[0],
                    'counted_count': counts.get(opname.id, (0, 0))[1],
                },
            )
            for opname, location_name in rows
        ],
        total=total,
    )


def _line_counts(
    session: Session, opname_ids: list[int | None]
) -> dict[int, tuple[int, int]]:
    """Per session: how many lines, and how many of them are counted."""
    rows = session.exec(
        select(
            OpnameLine.opname_id,
            func.count(),
            func.count(col(OpnameLine.first_counted_at)),
        )
        .where(col(OpnameLine.opname_id).in_(opname_ids))
        .group_by(col(OpnameLine.opname_id))
    ).all()
    return {opname_id: (n, counted) for opname_id, n, counted in rows}


def is_checker(session: Session, opname: StockOpname, user: User) -> bool:
    return session.get(OpnameChecker, (opname.id, user.id)) is not None


def revealed(session: Session, opname: StockOpname, user: User) -> bool:
    """Blind Count: no System Quantity or Variance before Review, and never
    to a Checker of the session (rule 4)."""
    return opname.status != OpnameStatus.counting and not is_checker(
        session, opname, user
    )


def opname_public(
    session: Session, opname: StockOpname, *, user: User
) -> OpnamePublic:
    location = session.get(Location, opname.location_id)
    assert location is not None
    assert opname.id is not None
    checker_rows = session.exec(
        select(User)
        .join(OpnameChecker)
        .where(OpnameChecker.opname_id == opname.id)
        .order_by(col(User.full_name))
    ).all()
    line_count, counted_count = _line_counts(session, [opname.id]).get(
        opname.id, (0, 0)
    )
    recount_count = session.exec(
        select(func.count())
        .select_from(OpnameLine)
        .where(
            OpnameLine.opname_id == opname.id,
            col(OpnameLine.recount).is_(True),
        )
    ).one()
    show = revealed(session, opname, user)
    totals: dict[str, Any] = {
        'shortage_count': None,
        'shortage_value': None,
        'surplus_count': None,
        'surplus_value': None,
    }
    if show:
        totals = _variance_totals(session, opname)
    return OpnamePublic.model_validate(
        opname,
        update={
            'location_name': location.name,
            'opened_by_name': documents.user_name(session, opname.opened_by),
            'counting_closed_by_name': documents.user_name(
                session, opname.counting_closed_by
            ),
            'approved_by_name': documents.user_name(
                session, opname.approved_by
            ),
            'cancelled_by_name': documents.user_name(
                session, opname.cancelled_by
            ),
            'checkers': [
                StaffOption.model_validate(user) for user in checker_rows
            ],
            'line_count': line_count,
            'counted_count': counted_count,
            'recount_count': recount_count,
            'revealed': show,
            'can_approve': can_approve(session, opname, user),
            **totals,
            'unknown_barcodes': _unknown_barcodes(session, opname.id),
            'reversal': documents.reversal_public(
                session, DOCUMENT_TYPE, opname.id
            ),
        },
    )


def can_approve(session: Session, opname: StockOpname, user: User) -> bool:
    """The approver is an Owner or Admin who was not a Checker (rule 10)."""
    return user.role in (Role.owner, Role.admin) and not is_checker(
        session, opname, user
    )


def _unknown_barcodes(
    session: Session, opname_id: int
) -> list[UnknownBarcodePublic]:
    scans = session.exec(
        select(UnknownBarcode, User.full_name)
        .join(User, col(UnknownBarcode.scanned_by) == User.id)
        .where(UnknownBarcode.opname_id == opname_id)
        .order_by(col(UnknownBarcode.id).desc())
    ).all()
    by_code: dict[str, UnknownBarcodePublic] = {}
    for scan, name in scans:
        if scan.code in by_code:
            by_code[scan.code].times += 1
        else:
            by_code[scan.code] = UnknownBarcodePublic(
                code=scan.code,
                times=1,
                last_scanned_by_name=name,
                last_scanned_at=scan.scanned_at,
            )
    return list(by_code.values())


def _variance_totals(session: Session, opname: StockOpname) -> dict[str, Any]:
    shortage_count = surplus_count = 0
    shortage_value = surplus_value = ZERO
    for line, sku, balance in _variance_rows(session, opname):
        value = _variance_value(opname, line, sku, balance) or ZERO
        if _variance(line) < 0:
            shortage_count += 1
            shortage_value += -value
        else:
            surplus_count += 1
            surplus_value += value
    return {
        'shortage_count': shortage_count,
        'shortage_value': shortage_value,
        'surplus_count': surplus_count,
        'surplus_value': surplus_value,
    }


def _variance_rows(
    session: Session, opname: StockOpname
) -> list[tuple[OpnameLine, Sku, StockBalance | None]]:
    """Counted lines whose Physical Quantity differs from the snapshot."""
    return list(
        session.exec(
            select(OpnameLine, Sku, StockBalance)
            .join(Sku, col(OpnameLine.sku_id) == Sku.id)
            .join(
                StockBalance,
                and_(
                    col(StockBalance.sku_id) == OpnameLine.sku_id,
                    col(StockBalance.location_id) == opname.location_id,
                ),
                isouter=True,
            )
            .where(
                OpnameLine.opname_id == opname.id,
                col(OpnameLine.first_counted_at).is_not(None),
                col(OpnameLine.physical_quantity)
                != col(OpnameLine.system_quantity),
            )
            .order_by(col(OpnameLine.sku_id))
        ).all()
    )


def _variance(line: OpnameLine) -> Decimal:
    """Physical Quantity minus the snapshot; zero while uncounted."""
    if line.system_quantity is None:
        return ZERO
    return line.physical_quantity - line.system_quantity


def _unit_cost(
    opname: StockOpname,
    line: OpnameLine,
    sku: Sku,
    balance: StockBalance | None,
) -> Decimal | None:
    """What one unit of this line's Variance is worth, None if unknown.

    Opening stock is at its opening cost; a Surplus by costing rule 5 (or the
    cost entered when the SKU never had one). A Shortage is estimated at the
    average cost; approval takes it out by the Costing Method.
    """
    if opname.is_opening:
        return line.unit_cost
    if _variance(line) > 0:
        return costing.found_unit_cost(sku, balance) or line.unit_cost
    if balance is not None and balance.quantity > 0:
        return costing.money(balance.value / balance.quantity)
    return sku.latest_unit_cost


def _variance_value(
    opname: StockOpname,
    line: OpnameLine,
    sku: Sku,
    balance: StockBalance | None,
) -> Decimal | None:
    if line.adjusted_value is not None:
        return line.adjusted_value
    unit_cost = _unit_cost(opname, line, sku, balance)
    if unit_cost is None:
        return None
    return costing.money(_variance(line) * unit_cost)


def list_lines(
    session: Session,
    opname: StockOpname,
    filters: OpnameLineFilter,
    *,
    user: User,
) -> OpnameLinePage:
    show = revealed(session, opname, user)
    conditions: list[Any] = [OpnameLine.opname_id == opname.id]
    counted = col(OpnameLine.first_counted_at).is_not(None)
    if filters.show == LineShow.uncounted:
        conditions.append(col(OpnameLine.first_counted_at).is_(None))
    elif filters.show == LineShow.counted:
        conditions.append(counted)
    elif filters.show in (LineShow.variance, LineShow.needs_cost):
        if not show:
            raise ForbiddenError(
                'Selisih baru terlihat setelah penghitungan ditutup, dan '
                'tidak untuk checker opname ini.'
            )
        has_variance = and_(
            counted,
            col(OpnameLine.physical_quantity)
            != col(OpnameLine.system_quantity),
        )
        conditions.append(
            or_(has_variance, col(OpnameLine.recount).is_(True))
            if filters.show == LineShow.variance
            else has_variance
        )
    search = (filters.search or '').strip()
    if search:
        conditions.append(
            or_(
                col(Product.name).icontains(search, autoescape=True),
                col(Sku.code).icontains(search, autoescape=True),
                col(Sku.barcode).icontains(search, autoescape=True),
            )
        )

    query = (
        select(OpnameLine, Sku, Product.name, StockBalance)
        .join(Sku, col(OpnameLine.sku_id) == Sku.id)
        .join(Product, col(Sku.product_id) == Product.id)
        .join(
            StockBalance,
            and_(
                col(StockBalance.sku_id) == OpnameLine.sku_id,
                col(StockBalance.location_id) == opname.location_id,
            ),
            isouter=True,
        )
        .where(*conditions)
        .order_by(col(Product.name), col(Sku.id))
    )
    rows = session.exec(query).all()
    if filters.show == LineShow.needs_cost:
        # Whether a cost is known depends on the Costing Method and balance.
        rows = [
            row
            for row in rows
            if _unit_cost(opname, row[0], row[1], row[3]) is None
            and _variance(row[0]) > 0
        ]
    page = rows[filters.offset : filters.offset + filters.limit]
    names = _charged_names(session, [line for line, *_ in page])
    return OpnameLinePage(
        items=[
            _line_public(opname, line, sku, name, balance, show, names)
            for line, sku, name, balance in page
        ],
        total=len(rows),
    )


def line_public(
    session: Session, opname: StockOpname, line: OpnameLine, *, user: User
) -> OpnameLinePublic:
    session.refresh(line)
    sku = session.get(Sku, line.sku_id)
    assert sku is not None
    balance = session.get(StockBalance, (sku.id, opname.location_id))
    return _line_public(
        opname,
        line,
        sku,
        sku.product.name,
        balance,
        revealed(session, opname, user),
        _charged_names(session, [line]),
    )


def _charged_names(
    session: Session, lines: list[OpnameLine]
) -> dict[int, str]:
    ids = {line.charged_user_id for line in lines if line.charged_user_id}
    if not ids:
        return {}
    users = session.exec(select(User).where(col(User.id).in_(ids))).all()
    return {user.id: user.full_name for user in users if user.id}


def _line_public(
    opname: StockOpname,
    line: OpnameLine,
    sku: Sku,
    product_name: str,
    balance: StockBalance | None,
    show: bool,
    charged_names: dict[int, str],
) -> OpnameLinePublic:
    public = OpnameLinePublic(
        id=line.id or 0,
        sku_id=line.sku_id,
        product_name=product_name,
        size=sku.size,
        color=sku.color,
        code=sku.code,
        barcode=sku.barcode,
        stock_unit=sku.stock_unit,
        counted=line.first_counted_at is not None,
        recount=line.recount,
    )
    if not show:
        return public
    counted = line.first_counted_at is not None
    variance = _variance(line)
    unit_cost = _unit_cost(opname, line, sku, balance)
    public.system_quantity = line.system_quantity
    public.physical_quantity = line.physical_quantity if counted else None
    public.variance = variance if counted else None
    public.moved_while_counting = line.moved_while_counting
    public.unit_cost = unit_cost
    public.needs_cost = counted and variance > 0 and unit_cost is None
    public.variance_value = (
        _variance_value(opname, line, sku, balance) if variance else ZERO
    )
    public.entered_unit_cost = line.unit_cost
    public.shortage_reason = line.shortage_reason
    public.resolution = line.resolution
    public.charged_user_id = line.charged_user_id
    public.charged_user_name = charged_names.get(line.charged_user_id or 0)
    public.charge_amount = line.charge_amount
    return public


# Counting


def counting_sessions(session: Session, user: User) -> list[CountingSummary]:
    """Unfinished sessions this user is a Checker in."""
    rows = session.exec(
        select(StockOpname, Location.name)
        .join(Location)
        .join(OpnameChecker)
        .where(
            OpnameChecker.user_id == user.id,
            col(StockOpname.status).in_(UNFINISHED),
        )
        .order_by(col(StockOpname.id).desc())
    ).all()
    return [
        CountingSummary.model_validate(
            opname,
            update={
                'location_name': location_name,
                'can_count': _can_count(session, opname),
            },
        )
        for opname, location_name in rows
    ]


def _can_count(session: Session, opname: StockOpname) -> bool:
    """Counting is open, or Review is waiting for a Recount."""
    if opname.status == OpnameStatus.counting:
        return True
    if opname.status != OpnameStatus.review:
        return False
    waiting = session.exec(
        select(OpnameLine.id)
        .where(
            OpnameLine.opname_id == opname.id,
            col(OpnameLine.recount).is_(True),
        )
        .limit(1)
    ).first()
    return waiting is not None


def count_sheet(
    session: Session, opname: StockOpname, *, user: User
) -> CountSheet:
    _require_checker(session, opname, user)
    location = session.get(Location, opname.location_id)
    assert location is not None
    mine = (
        CountEntry.counted_by == user.id,
        col(CountEntry.cancelled_at).is_(None),
        OpnameLine.opname_id == opname.id,
    )
    entry_count, sku_count = session.exec(
        select(func.count(), func.count(func.distinct(CountEntry.line_id)))
        .select_from(CountEntry)
        .join(OpnameLine)
        .where(*mine)
    ).one()
    rows = session.exec(
        select(CountEntry, Sku, Product.name)
        .select_from(CountEntry)
        .join(OpnameLine, col(CountEntry.line_id) == OpnameLine.id)
        .join(Sku, col(OpnameLine.sku_id) == Sku.id)
        .join(Product, col(Sku.product_id) == Product.id)
        .where(*mine)
        .order_by(col(CountEntry.id).desc())
        .limit(MY_ENTRIES_SHOWN)
    ).all()
    return CountSheet(
        id=opname.id or 0,
        number=opname.number,
        status=opname.status,
        scope_label=opname.scope_label,
        location_name=location.name,
        can_count=_can_count(session, opname),
        entries=[_my_entry(entry, sku, name) for entry, sku, name in rows],
        entry_count=entry_count,
        sku_count=sku_count,
    )


def _my_entry(entry: CountEntry, sku: Sku, product_name: str) -> MyCountEntry:
    return MyCountEntry(
        id=entry.id or 0,
        sku_id=sku.id or 0,
        product_name=product_name,
        size=sku.size,
        color=sku.color,
        code=sku.code,
        stock_unit=sku.stock_unit,
        quantity=entry.quantity,
        counted_at=entry.counted_at,
    )


def find_skus(
    session: Session, opname: StockOpname, search: str, *, user: User
) -> list[CountSkuOption]:
    """SKUs in Scope matching a name, for items without a Barcode."""
    _require_checker(session, opname, user)
    search = search.strip()
    if not search:
        return []
    rows = session.exec(
        select(Sku, Product.name)
        .join(OpnameLine, col(OpnameLine.sku_id) == Sku.id)
        .join(Product, col(Sku.product_id) == Product.id)
        .where(
            OpnameLine.opname_id == opname.id,
            or_(
                col(Product.name).icontains(search, autoescape=True),
                col(Sku.code).icontains(search, autoescape=True),
                col(Sku.barcode).icontains(search, autoescape=True),
            ),
        )
        .order_by(col(Product.name), col(Sku.id))
        .limit(20)
    ).all()
    return [
        CountSkuOption.model_validate(sku, update={'product_name': name})
        for sku, name in rows
    ]


def add_count(
    session: Session,
    opname: StockOpname,
    count_in: CountCreate,
    *,
    user: User,
) -> MyCountEntry:
    _require_checker(session, opname, user)
    opname = _share_lock(session, opname)
    _require_countable(opname)
    assert opname.id is not None

    if count_in.code is not None:
        code = count_in.code.strip()
        sku = session.exec(
            select(Sku).where(
                or_(
                    Sku.barcode == code,
                    func.lower(Sku.code) == code.lower(),
                )
            )
        ).first()
        if sku is None:
            assert user.id is not None
            # Kept even though the count is refused (rule 7).
            session.add(
                UnknownBarcode(
                    opname_id=opname.id, code=code[:64], scanned_by=user.id
                )
            )
            session.commit()
            raise NotFoundError(
                f'Barcode {code} tidak dikenal. Sudah dicatat untuk Admin.'
            )
    else:
        sku = session.get(Sku, count_in.sku_id)
        if sku is None:
            raise NotFoundError('SKU tidak ditemukan.')

    line = _lock_line(session, opname.id, sku.id)
    label = sku_label(sku.product.name, sku.size, sku.color)
    if line is None:
        raise ConflictError(f'{label} tidak termasuk opname ini.')
    if opname.status == OpnameStatus.review and not line.recount:
        raise ConflictError(
            f'{label} sudah selesai dihitung. Saat peninjauan hanya barang '
            'yang diminta hitung ulang yang bisa dihitung.'
        )

    entry = _count(session, opname, line, count_in.quantity, user=user)
    session.commit()
    return _my_entry(entry, sku, sku.product.name)


def _count(
    session: Session,
    opname: StockOpname,
    line: OpnameLine,
    quantity: Decimal,
    *,
    user: User,
) -> CountEntry:
    """Add a Count Entry to a locked line."""
    assert user.id is not None
    assert line.id is not None
    now = utc_now()
    if line.first_counted_at is None:
        # The snapshot every later count of this line is measured against
        # (rule 5).
        balance = session.exec(
            select(StockBalance)
            .where(
                StockBalance.sku_id == line.sku_id,
                StockBalance.location_id == opname.location_id,
            )
            .execution_options(populate_existing=True)
        ).first()
        line.system_quantity = balance.quantity if balance else ZERO
        line.first_counted_at = now
    elif not line.moved_while_counting:
        # Sold, returned or received since the first count (rule 8).
        moved = session.exec(
            select(StockMovement.id)
            .where(
                StockMovement.sku_id == line.sku_id,
                StockMovement.location_id == opname.location_id,
                col(StockMovement.created_at) > line.first_counted_at,
            )
            .limit(1)
        ).first()
        line.moved_while_counting = moved is not None
    line.physical_quantity += quantity
    session.add(line)
    entry = CountEntry(
        line_id=line.id, quantity=quantity, counted_by=user.id, counted_at=now
    )
    session.add(entry)
    session.flush()
    return entry


def cancel_count(
    session: Session, opname: StockOpname, entry_id: int, *, user: User
) -> None:
    """A Checker takes back one of their own entries, e.g. a double scan."""
    _require_checker(session, opname, user)
    opname = _share_lock(session, opname)
    _require_countable(opname)
    entry = session.get(CountEntry, entry_id)
    line = session.get(OpnameLine, entry.line_id) if entry else None
    if (
        entry is None
        or line is None
        or line.opname_id != opname.id
        or entry.counted_by != user.id
        or entry.cancelled_at is not None
    ):
        raise NotFoundError('Hitungan tidak ditemukan.')
    assert opname.id is not None
    line = _lock_line(session, opname.id, line.sku_id)
    assert line is not None
    if opname.status == OpnameStatus.review and not line.recount:
        raise ConflictError('Hitungan ini sudah ditinjau.')
    entry.cancelled_at = utc_now()
    entry.cancelled_by = user.id
    session.add(entry)
    line.physical_quantity -= entry.quantity
    if not _active_entries(session, line):
        _clear_count(line)
    session.add(line)
    session.commit()


def _active_entries(session: Session, line: OpnameLine) -> list[CountEntry]:
    return list(
        session.exec(
            select(CountEntry).where(
                CountEntry.line_id == line.id,
                col(CountEntry.cancelled_at).is_(None),
            )
        ).all()
    )


def _clear_count(line: OpnameLine) -> None:
    """Back to uncounted: the next count takes a fresh snapshot."""
    line.system_quantity = None
    line.first_counted_at = None
    line.physical_quantity = ZERO
    line.moved_while_counting = False


def _require_checker(
    session: Session, opname: StockOpname, user: User
) -> None:
    if not is_checker(session, opname, user):
        raise ForbiddenError(
            f'Anda tidak ditugaskan menghitung di {opname.number}.'
        )


def _require_countable(opname: StockOpname) -> None:
    if opname.status not in UNFINISHED:
        raise ConflictError(f'Penghitungan {opname.number} sudah ditutup.')


def _share_lock(session: Session, opname: StockOpname) -> StockOpname:
    """Re-read the session and keep its status from changing until commit.

    Counts take a shared lock so they don't wait for each other; closing,
    approving and cancelling take an exclusive one.
    """
    locked = session.get(
        StockOpname,
        opname.id,
        with_for_update={'read': True},
        populate_existing=True,
    )
    assert locked is not None
    return locked


def _lock_line(
    session: Session, opname_id: int, sku_id: int | None
) -> OpnameLine | None:
    return session.exec(
        select(OpnameLine)
        .where(OpnameLine.opname_id == opname_id, OpnameLine.sku_id == sku_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


# Changing the session


def cancel(session: Session, opname: StockOpname, *, actor: User) -> None:
    """Drop an unfinished session. Nothing in stock changed, so nothing is
    undone."""
    assert opname.id is not None
    opname = documents.lock(session, StockOpname, opname.id)
    if opname.status not in UNFINISHED:
        raise ConflictError(
            f'Stok opname {opname.number} sudah '
            f'{STATUS_WORDS[opname.status]} dan tidak bisa dibatalkan.'
        )
    opname.status = OpnameStatus.cancelled
    opname.cancelled_by = actor.id
    opname.cancelled_at = utc_now()
    session.add(opname)
    activity_log.record(
        session,
        actor=actor,
        action='stock_opname.cancel',
        summary=f'Membatalkan stok opname {opname.number}.',
        entity_type=DOCUMENT_TYPE,
        entity_id=opname.id,
    )
    session.commit()


STATUS_WORDS = {
    OpnameStatus.counting: 'dalam penghitungan',
    OpnameStatus.review: 'dalam peninjauan',
    OpnameStatus.approved: 'disetujui',
    OpnameStatus.cancelled: 'dibatalkan',
    OpnameStatus.reversed: 'dibatalkan setelah disetujui',
}


def confirm_zero(
    session: Session, opname: StockOpname, line_ids: list[int], *, actor: User
) -> int:
    """The Admin confirms uncounted lines as none found (rule 9).

    Lines counted in the meantime are left alone. Returns how many were
    confirmed.
    """
    opname = _share_lock(session, opname)
    _require_countable(opname)
    assert opname.id is not None
    lines = session.exec(
        select(OpnameLine)
        .where(
            OpnameLine.opname_id == opname.id,
            col(OpnameLine.id).in_(line_ids),
        )
        .order_by(col(OpnameLine.sku_id))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if len(lines) != len(set(line_ids)):
        raise NotFoundError('SKU tidak ditemukan dalam opname ini.')
    confirmed = 0
    for line in lines:
        if line.first_counted_at is not None:
            continue
        if opname.status == OpnameStatus.review and not line.recount:
            continue
        _count(session, opname, line, ZERO, user=actor)
        confirmed += 1
    if confirmed:
        activity_log.record(
            session,
            actor=actor,
            action='stock_opname.confirm_zero',
            summary=(
                f'Mengonfirmasi {confirmed} SKU tidak ditemukan (nol) di '
                f'stok opname {opname.number}.'
            ),
            entity_type=DOCUMENT_TYPE,
            entity_id=opname.id,
        )
    session.commit()
    return confirmed


def close_counting(
    session: Session, opname: StockOpname, *, actor: User
) -> StockOpname:
    """Counting -> Review, once every line is counted or confirmed zero."""
    assert opname.id is not None
    opname = documents.lock(session, StockOpname, opname.id)
    if opname.status != OpnameStatus.counting:
        raise ConflictError(
            f'Stok opname {opname.number} sudah {STATUS_WORDS[opname.status]}.'
        )
    uncounted = session.exec(
        select(func.count())
        .select_from(OpnameLine)
        .where(
            OpnameLine.opname_id == opname.id,
            col(OpnameLine.first_counted_at).is_(None),
        )
    ).one()
    if uncounted:
        raise ConflictError(
            f'Masih ada {uncounted} SKU yang belum dihitung. Hitung, atau '
            'konfirmasi nol jika memang tidak ada barangnya.'
        )
    opname.status = OpnameStatus.review
    opname.counting_closed_by = actor.id
    opname.counting_closed_at = utc_now()
    session.add(opname)
    activity_log.record(
        session,
        actor=actor,
        action='stock_opname.close_counting',
        summary=f'Menutup penghitungan stok opname {opname.number}.',
        entity_type=DOCUMENT_TYPE,
        entity_id=opname.id,
    )
    session.commit()
    return opname


def get_line(
    session: Session, opname: StockOpname, line_id: int
) -> OpnameLine:
    line = session.get(OpnameLine, line_id)
    if line is None or line.opname_id != opname.id:
        raise NotFoundError('SKU tidak ditemukan dalam opname ini.')
    return line


def recount(
    session: Session, opname: StockOpname, line: OpnameLine, *, actor: User
) -> None:
    """Send one line back to the Checkers; the rest waits in Review (rule
    11). Its entries are cancelled, not deleted."""
    opname = _lock_for_review(session, opname, actor)
    assert opname.id is not None
    locked = _lock_line(session, opname.id, line.sku_id)
    assert locked is not None
    line = locked
    now = utc_now()
    for entry in _active_entries(session, line):
        entry.cancelled_at = now
        entry.cancelled_by = actor.id
        session.add(entry)
    _clear_count(line)
    line.recount = True
    line.shortage_reason = None
    line.resolution = None
    line.charged_user_id = None
    line.charge_amount = None
    session.add(line)
    sku = session.get(Sku, line.sku_id)
    assert sku is not None
    activity_log.record(
        session,
        actor=actor,
        action='stock_opname.recount',
        summary=(
            f'Meminta hitung ulang '
            f'{sku_label(sku.product.name, sku.size, sku.color)} di stok '
            f'opname {opname.number}.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=opname.id,
    )
    session.commit()


def _lock_for_review(
    session: Session, opname: StockOpname, actor: User
) -> StockOpname:
    """Lock a session in Review for its approver."""
    assert opname.id is not None
    opname = documents.lock(session, StockOpname, opname.id)
    if opname.status != OpnameStatus.review:
        raise ConflictError(
            f'Stok opname {opname.number} {STATUS_WORDS[opname.status]}, '
            'bukan dalam peninjauan.'
        )
    if not can_approve(session, opname, actor):
        raise ForbiddenError(
            'Peninjauan dilakukan oleh Pemilik atau Admin yang tidak ikut '
            'menghitung di opname ini.'
        )
    return opname


# Approval


def save_resolution(
    session: Session,
    opname: StockOpname,
    line: OpnameLine,
    data: LineResolutionSave,
    *,
    actor: User,
) -> None:
    """The approver's decision on one line: why a Shortage happened, who
    bears it, and a unit cost where none is known (rules 12-14, 19)."""
    opname = _lock_for_review(session, opname, actor)
    charged = data.resolution == Resolution.employee_charge
    decision = (data.resolution, data.charged_user_id, data.charge_amount)
    unchanged = decision == (
        line.resolution,
        line.charged_user_id,
        line.charge_amount,
    )
    if charged and not unchanged and actor.role != Role.owner:
        raise ForbiddenError(
            'Hanya Pemilik yang boleh membebankan selisih ke karyawan.'
        )
    if charged and data.charged_user_id is not None:
        employee = session.get(User, data.charged_user_id)
        if employee is None:
            raise NotFoundError('Karyawan tidak ditemukan.')
        if not employee.is_active and not unchanged:
            raise ConflictError(f'{employee.full_name} sudah nonaktif.')
    line.shortage_reason = data.shortage_reason
    line.resolution = data.resolution
    line.charged_user_id = data.charged_user_id if charged else None
    line.charge_amount = data.charge_amount if charged else None
    line.unit_cost = data.unit_cost
    session.add(line)
    session.commit()


def approve(
    session: Session, opname: StockOpname, *, actor: User
) -> StockOpname:
    """Write one Stock Movement per Variance on top of today's System
    Quantity, create the Employee Charges, and close the session for good
    (rules 15-16, 20)."""
    opname = _lock_for_review(session, opname, actor)
    assert opname.id is not None
    rows = session.exec(
        select(OpnameLine, Sku)
        .join(Sku, col(OpnameLine.sku_id) == Sku.id)
        .where(OpnameLine.opname_id == opname.id)
        # SKU order, like every other stock document, avoids deadlocks.
        .order_by(col(OpnameLine.sku_id))
    ).all()
    waiting = sum(1 for line, _ in rows if line.first_counted_at is None)
    if waiting:
        raise ConflictError(f'{waiting} SKU masih menunggu hitung ulang.')
    problems = [
        problem
        for line, sku in rows
        if (problem := _approval_problem(session, opname, line, sku))
    ]
    if problems:
        more = len(problems) - 5
        listed = '; '.join(problems[:5]) + (
            f'; dan {more} lagi' if more > 0 else ''
        )
        raise ConflictError(f'Belum bisa disetujui. {listed}.')

    source = costing.Source(DOCUMENT_TYPE, opname.id, opname.number)
    reason = (
        MovementReason.opening if opname.is_opening else MovementReason.opname
    )
    shortages = surpluses = charges = 0
    for line, sku in rows:
        variance = _variance(line)
        if variance == 0:
            continue
        assert sku.id is not None
        if variance > 0:
            surpluses += 1
            if opname.is_opening:
                assert line.unit_cost is not None
                movement = costing.receive(
                    session,
                    sku=sku,
                    location_id=opname.location_id,
                    quantity=variance,
                    value=costing.money(variance * line.unit_cost),
                    reason=reason,
                    source=source,
                    actor=actor,
                )
            else:
                movement = costing.found(
                    session,
                    sku=sku,
                    location_id=opname.location_id,
                    quantity=variance,
                    reason=reason,
                    source=source,
                    actor=actor,
                    unit_cost=line.unit_cost,
                )
        else:
            shortages += 1
            movement = costing.issue(
                session,
                sku=sku,
                location_id=opname.location_id,
                quantity=-variance,
                reason=reason,
                source=source,
                actor=actor,
            )
        line.adjusted_value = movement.value
        if variance < 0 and not opname.is_opening:
            line.resolution = line.resolution or Resolution.company_loss
            if line.resolution == Resolution.employee_charge:
                charges += 1
                _charge(session, opname, line, sku, movement.value, actor)
        session.add(line)

    opname.status = OpnameStatus.approved
    opname.approved_by = actor.id
    opname.approved_at = utc_now()
    session.add(opname)
    activity_log.record(
        session,
        actor=actor,
        action='stock_opname.approve',
        summary=(
            f'Menyetujui {"opname awal" if opname.is_opening else "stok opname"} '
            f'{opname.number}: {shortages} SKU kurang, {surpluses} SKU lebih, '
            f'{charges} ganti rugi karyawan.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=opname.id,
    )
    session.commit()
    return opname


def _approval_problem(
    session: Session, opname: StockOpname, line: OpnameLine, sku: Sku
) -> str | None:
    """What still stops this line from being approved, if anything."""
    variance = _variance(line)
    label = sku_label(sku.product.name, sku.size, sku.color)
    if variance > 0:
        balance = session.get(StockBalance, (sku.id, opname.location_id))
        if _unit_cost(opname, line, sku, balance) is None:
            return f'{label}: isi harga per {sku.stock_unit}'
    if variance < 0 and not opname.is_opening:
        if line.shortage_reason is None:
            return f'{label}: pilih alasan selisih kurang'
        if (
            line.resolution == Resolution.employee_charge
            and line.charged_user_id is None
        ):
            return f'{label}: pilih karyawan yang menanggung'
    return None


def _charge(
    session: Session,
    opname: StockOpname,
    line: OpnameLine,
    sku: Sku,
    value: Decimal,
    actor: User,
) -> None:
    """The Employee Charge for a Shortage: the amount the Owner set, or the
    Shortage at the cost it left stock at (rule 13)."""
    assert line.charged_user_id is not None
    assert opname.id is not None
    amount = (
        line.charge_amount
        if line.charge_amount is not None
        else int(costing.money(-value).to_integral_value())
    )
    label = sku_label(sku.product.name, sku.size, sku.color)
    shortage = -_variance(line)
    session.add(
        EmployeeCharge(
            user_id=line.charged_user_id,
            amount=amount,
            description=(
                f'Selisih kurang {label}: {shortage.normalize():f} '
                f'{sku.stock_unit}'
            )[:300],
            source_type=DOCUMENT_TYPE,
            source_id=opname.id,
            source_number=opname.number,
            created_by=actor.id,
        )
    )


def reverse(
    session: Session, opname: StockOpname, reason: str, *, actor: User
) -> StockOpname:
    """Undo an approved session's adjustments and cancel its Employee
    Charges that are still outstanding (rule 17)."""
    assert opname.id is not None
    opname = documents.lock(session, StockOpname, opname.id)
    assert opname.id is not None
    if opname.status != OpnameStatus.approved:
        raise ConflictError(
            f'Stok opname {opname.number} {STATUS_WORDS[opname.status]}; '
            'hanya opname yang sudah disetujui yang bisa dibatalkan.'
        )
    documents.write_reversal(
        session,
        document_type=DOCUMENT_TYPE,
        document_id=opname.id,
        label=f'stok opname {opname.number}',
        reason=reason,
        actor=actor,
    )
    employee_charges.cancel_outstanding(
        session, source_type=DOCUMENT_TYPE, source_id=opname.id
    )
    opname.status = OpnameStatus.reversed
    session.add(opname)
    session.commit()
    return opname
