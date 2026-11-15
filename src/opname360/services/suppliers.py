from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from opname360.core.errors import AppError, ConflictError, NotFoundError
from opname360.models import Supplier, SupplierCreate, SupplierUpdate, User
from opname360.services import activity_log


def _clean(value: str | None) -> str | None:
    return (value or '').strip() or None


def list_suppliers(session: Session) -> Sequence[Supplier]:
    return session.exec(select(Supplier).order_by(col(Supplier.name))).all()


def get_supplier(session: Session, supplier_id: int) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError('Pemasok tidak ditemukan.')
    return supplier


def create_supplier(
    session: Session, supplier_in: SupplierCreate, *, actor: User
) -> Supplier:
    name = _checked_name(session, supplier_in.name)
    supplier = Supplier(
        name=name,
        phone=_clean(supplier_in.phone),
        address=_clean(supplier_in.address),
    )
    session.add(supplier)
    session.flush()
    activity_log.record(
        session,
        actor=actor,
        action='supplier.create',
        summary=f'Menambah pemasok {name}.',
        entity_type='supplier',
        entity_id=supplier.id,
    )
    session.commit()
    return supplier


def update_supplier(
    session: Session,
    supplier: Supplier,
    supplier_in: SupplierUpdate,
    *,
    actor: User,
) -> Supplier:
    sent = supplier_in.model_dump(exclude_unset=True)
    if sent.get('name') is not None:
        supplier.name = _checked_name(session, sent['name'], exclude=supplier)
    if 'phone' in sent:
        supplier.phone = _clean(sent['phone'])
    if 'address' in sent:
        supplier.address = _clean(sent['address'])
    if sent.get('is_active') is not None:
        supplier.is_active = sent['is_active']
    session.add(supplier)
    activity_log.record(
        session,
        actor=actor,
        action='supplier.update',
        summary=(
            f'Mengubah pemasok {supplier.name}'
            + ('' if supplier.is_active else ' (nonaktif)')
            + '.'
        ),
        entity_type='supplier',
        entity_id=supplier.id,
    )
    session.commit()
    return supplier


def _checked_name(
    session: Session, name: str, *, exclude: Supplier | None = None
) -> str:
    name = name.strip()
    if not name:
        raise AppError('Nama pemasok wajib diisi.')
    query = select(Supplier.id).where(
        func.lower(Supplier.name) == name.lower()
    )
    if exclude is not None:
        query = query.where(Supplier.id != exclude.id)
    if session.exec(query).first() is not None:
        raise ConflictError(f'Pemasok "{name}" sudah ada.')
    return name
