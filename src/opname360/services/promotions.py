"""Promotions: discounts that apply by themselves (rules 7 and 18)."""

from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError, NotFoundError
from opname360.core.formatting import ANGLE, rupiah, sku_label
from opname360.models import (
    Category,
    DiscountKind,
    Product,
    Promotion,
    PromotionFilter,
    PromotionPage,
    PromotionPublic,
    PromotionSave,
    PromotionStatus,
    PromotionTarget,
    PromotionTargetPublic,
    ReceiptLine,
    Sku,
    SubCategory,
    TargetKind,
    User,
)
from opname360.models._types import utc_now
from opname360.services import activity_log, documents


DOCUMENT_TYPE = 'promotion'
TARGET_MODELS = {
    TargetKind.skus: Sku,
    TargetKind.products: Product,
    TargetKind.sub_categories: SubCategory,
    TargetKind.categories: Category,
}


def status_of(promotion: Promotion, now: datetime) -> PromotionStatus:
    if promotion.starts_at > now:
        return PromotionStatus.upcoming
    if promotion.ends_at <= now:
        return PromotionStatus.ended
    return PromotionStatus.running


def describe(promotion: Promotion) -> str:
    """'10%' or 'Rp 5.000'."""
    if promotion.discount_kind == DiscountKind.percentage:
        return f'{promotion.value}%'
    return rupiah(promotion.value)


def list_promotions(
    session: Session, filters: PromotionFilter
) -> PromotionPage:
    now = utc_now()
    query = select(Promotion)
    if filters.status == PromotionStatus.upcoming:
        query = query.where(col(Promotion.starts_at) > now)
    elif filters.status == PromotionStatus.running:
        query = query.where(
            col(Promotion.starts_at) <= now, col(Promotion.ends_at) > now
        )
    elif filters.status == PromotionStatus.ended:
        query = query.where(col(Promotion.ends_at) <= now)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    promotions = session.exec(
        query.order_by(col(Promotion.starts_at).desc(), col(Promotion.id))
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return PromotionPage(
        items=[promotion_public(session, p) for p in promotions], total=total
    )


def get_promotion(session: Session, promotion_id: int) -> Promotion:
    promotion = session.get(Promotion, promotion_id)
    if promotion is None:
        raise NotFoundError('Promo tidak ditemukan.')
    return promotion


def create_promotion(
    session: Session, promotion_in: PromotionSave, *, actor: User
) -> Promotion:
    promotion = Promotion(
        name=promotion_in.name,
        discount_kind=promotion_in.discount_kind,
        value=promotion_in.value,
        target_kind=promotion_in.target_kind,
        starts_at=promotion_in.starts_at,
        ends_at=promotion_in.ends_at,
        created_by=actor.id,
    )
    _apply(session, promotion, promotion_in)
    activity_log.record(
        session,
        actor=actor,
        action='promotion.create',
        summary=f'Membuat promo {promotion.name} ({describe(promotion)}).',
        entity_type=DOCUMENT_TYPE,
        entity_id=promotion.id,
    )
    session.commit()
    return promotion


def update_promotion(
    session: Session,
    promotion: Promotion,
    promotion_in: PromotionSave,
    *,
    actor: User,
) -> Promotion:
    """Only while no Receipt used it (rule 18)."""
    if is_used(session, promotion):
        raise ConflictError(
            f'Promo {promotion.name} sudah dipakai di struk, jadi tidak bisa '
            'diubah. Akhiri promo ini dan buat yang baru.'
        )
    _apply(session, promotion, promotion_in)
    activity_log.record(
        session,
        actor=actor,
        action='promotion.update',
        summary=f'Mengubah promo {promotion.name} ({describe(promotion)}).',
        entity_type=DOCUMENT_TYPE,
        entity_id=promotion.id,
    )
    session.commit()
    return promotion


def end_early(
    session: Session, promotion: Promotion, *, actor: User
) -> Promotion:
    """Stop it now; one that hasn't started never will."""
    now = utc_now()
    if status_of(promotion, now) == PromotionStatus.ended:
        raise ConflictError(f'Promo {promotion.name} sudah selesai.')
    promotion.ends_at = now
    promotion.starts_at = min(promotion.starts_at, now)
    session.add(promotion)
    activity_log.record(
        session,
        actor=actor,
        action='promotion.end',
        summary=f'Mengakhiri promo {promotion.name} lebih awal.',
        entity_type=DOCUMENT_TYPE,
        entity_id=promotion.id,
    )
    session.commit()
    return promotion


def is_used(session: Session, promotion: Promotion) -> bool:
    return (
        session.exec(
            select(ReceiptLine.id)
            .where(ReceiptLine.promotion_id == promotion.id)
            .limit(1)
        ).first()
        is not None
    )


def _apply(
    session: Session, promotion: Promotion, promotion_in: PromotionSave
) -> None:
    ids = list(dict.fromkeys(promotion_in.target_ids))
    model = TARGET_MODELS[promotion_in.target_kind]
    found = set(
        session.exec(select(model.id).where(col(model.id).in_(ids))).all()
    )
    if len(found) != len(ids):
        raise NotFoundError('Ada sasaran promo yang tidak ditemukan.')
    promotion.sqlmodel_update(
        promotion_in.model_dump(exclude={'target_ids'})
        | {'name': promotion_in.name.strip()}
    )
    for target in list(promotion.targets):
        session.delete(target)
    session.add(promotion)
    session.flush()
    assert promotion.id is not None
    for target_id in ids:
        session.add(
            PromotionTarget(promotion_id=promotion.id, target_id=target_id)
        )
    session.flush()
    session.refresh(promotion)


def promotion_public(
    session: Session, promotion: Promotion
) -> PromotionPublic:
    return PromotionPublic.model_validate(
        promotion,
        update={
            'targets': _target_labels(session, promotion),
            'status': status_of(promotion, utc_now()),
            'used': is_used(session, promotion),
            'created_by_name': documents.user_name(
                session, promotion.created_by
            ),
        },
    )


def _target_labels(
    session: Session, promotion: Promotion
) -> list[PromotionTargetPublic]:
    ids = [target.target_id for target in promotion.targets]
    model = TARGET_MODELS[promotion.target_kind]
    rows = session.exec(select(model).where(col(model.id).in_(ids))).all()
    labels = []
    for row in rows:
        if isinstance(row, Sku):
            label = sku_label(row.product.name, row.size, row.color)
        elif isinstance(row, SubCategory):
            label = f'{row.category.name} {ANGLE} {row.name}'
        else:
            label = row.name
        assert row.id is not None
        labels.append(PromotionTargetPublic(id=row.id, label=label))
    return sorted(labels, key=lambda target: target.label)


def best_discounts(
    session: Session, skus: list[Sku], at: datetime
) -> dict[int, tuple[Promotion, Decimal]]:
    """Per SKU, the running Promotion with the biggest discount on one unit,
    and that discount. They never add up, and never go below a zero price
    (rule 7)."""
    running = session.exec(
        select(Promotion)
        .where(col(Promotion.starts_at) <= at, col(Promotion.ends_at) > at)
        .order_by(col(Promotion.id))
    ).all()
    targets = {
        promotion.id: {target.target_id for target in promotion.targets}
        for promotion in running
    }
    best: dict[int, tuple[Promotion, Decimal]] = {}
    for sku in skus:
        assert sku.id is not None
        keys = {
            TargetKind.skus: sku.id,
            TargetKind.products: sku.product_id,
            TargetKind.sub_categories: sku.product.sub_category_id,
            TargetKind.categories: sku.product.sub_category.category_id,
        }
        for promotion in running:
            if keys[promotion.target_kind] not in targets[promotion.id]:
                continue
            discount = _unit_discount(promotion, sku.selling_price)
            if discount > 0 and (
                sku.id not in best or discount > best[sku.id][1]
            ):
                best[sku.id] = (promotion, discount)
    return best


def _unit_discount(promotion: Promotion, price: int) -> Decimal:
    if promotion.discount_kind == DiscountKind.percentage:
        return Decimal(price) * promotion.value / 100
    return Decimal(min(promotion.value, price))
