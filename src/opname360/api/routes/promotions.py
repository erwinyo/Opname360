from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    Promotion,
    PromotionFilter,
    PromotionPage,
    PromotionPublic,
    PromotionSave,
)
from opname360.services import promotions


router = APIRouter(
    prefix='/promotions',
    tags=['promotions'],
    dependencies=[Depends(require_admin)],
)


def get_promotion_or_404(
    session: SessionDep, promotion_id: Annotated[int, Path(ge=1)]
) -> Promotion:
    return promotions.get_promotion(session, promotion_id)


PromotionDep = Annotated[Promotion, Depends(get_promotion_or_404)]


@router.get('/')
def list_promotions(
    session: SessionDep, filters: Annotated[PromotionFilter, Query()]
) -> PromotionPage:
    return promotions.list_promotions(session, filters)


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_promotion(
    session: SessionDep, admin: AdminDep, promotion_in: PromotionSave
) -> PromotionPublic:
    promotion = promotions.create_promotion(session, promotion_in, actor=admin)
    return promotions.promotion_public(session, promotion)


@router.get('/{promotion_id}')
def read_promotion(
    session: SessionDep, promotion: PromotionDep
) -> PromotionPublic:
    return promotions.promotion_public(session, promotion)


@router.put('/{promotion_id}')
def update_promotion(
    session: SessionDep,
    admin: AdminDep,
    promotion: PromotionDep,
    promotion_in: PromotionSave,
) -> PromotionPublic:
    promotion = promotions.update_promotion(
        session, promotion, promotion_in, actor=admin
    )
    return promotions.promotion_public(session, promotion)


@router.post('/{promotion_id}/end')
def end_promotion(
    session: SessionDep, admin: AdminDep, promotion: PromotionDep
) -> PromotionPublic:
    """End it now. A Promotion already on a Receipt can only be ended."""
    promotion = promotions.end_early(session, promotion, actor=admin)
    return promotions.promotion_public(session, promotion)
