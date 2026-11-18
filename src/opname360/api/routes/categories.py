from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from opname360.api.deps import (
    AdminDep,
    OwnerDep,
    SessionDep,
    require_admin,
)
from opname360.models import (
    Category,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    CostingMethodSwitch,
    SubCategory,
    SubCategorySave,
)
from opname360.services import catalogue


router = APIRouter(
    prefix='/categories',
    tags=['categories'],
    dependencies=[Depends(require_admin)],
)


def get_category_or_404(
    session: SessionDep, category_id: Annotated[int, Path(ge=1)]
) -> Category:
    return catalogue.get_category(session, category_id)


def get_sub_category_or_404(
    session: SessionDep, sub_category_id: Annotated[int, Path(ge=1)]
) -> SubCategory:
    return catalogue.get_sub_category(session, sub_category_id)


CategoryDep = Annotated[Category, Depends(get_category_or_404)]
SubCategoryDep = Annotated[SubCategory, Depends(get_sub_category_or_404)]


@router.get('/')
def list_categories(session: SessionDep) -> list[CategoryPublic]:
    return catalogue.list_categories(session)


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_category(
    session: SessionDep, admin: AdminDep, category_in: CategoryCreate
) -> CategoryPublic:
    category = catalogue.create_category(session, category_in, actor=admin)
    return catalogue.category_public(session, category)


@router.patch('/{category_id}')
def update_category(
    session: SessionDep,
    admin: AdminDep,
    category: CategoryDep,
    category_in: CategoryUpdate,
) -> CategoryPublic:
    catalogue.update_category(session, category, category_in, actor=admin)
    return catalogue.category_public(session, category)


@router.post('/{category_id}/costing-method')
def switch_costing_method(
    session: SessionDep,
    owner: OwnerDep,
    category: CategoryDep,
    body: CostingMethodSwitch,
) -> CategoryPublic:
    """Only the Owner switches, from this moment on (ADR 0002)."""
    category = catalogue.switch_costing_method(
        session, category, body.costing_method, actor=owner
    )
    return catalogue.category_public(session, category)


@router.delete('/{category_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    session: SessionDep, admin: AdminDep, category: CategoryDep
) -> None:
    catalogue.delete_category(session, category, actor=admin)


@router.post(
    '/{category_id}/sub-categories', status_code=status.HTTP_201_CREATED
)
def create_sub_category(
    session: SessionDep,
    admin: AdminDep,
    category: CategoryDep,
    body: SubCategorySave,
) -> CategoryPublic:
    catalogue.create_sub_category(session, category, body.name, actor=admin)
    return catalogue.category_public(session, category)


@router.patch('/sub-categories/{sub_category_id}')
def rename_sub_category(
    session: SessionDep,
    admin: AdminDep,
    sub_category: SubCategoryDep,
    body: SubCategorySave,
) -> CategoryPublic:
    catalogue.rename_sub_category(
        session, sub_category, body.name, actor=admin
    )
    return catalogue.category_public(session, sub_category.category)


@router.delete(
    '/sub-categories/{sub_category_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_sub_category(
    session: SessionDep, admin: AdminDep, sub_category: SubCategoryDep
) -> None:
    catalogue.delete_sub_category(session, sub_category, actor=admin)
