from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import OwnerDep, SessionDep, get_current_user
from opname360.models import (
    PaymentMethod,
    PaymentMethodCreate,
    PaymentMethodPublic,
    PaymentMethodUpdate,
)
from opname360.services import payment_methods


router = APIRouter(
    prefix='/payment-methods',
    tags=['payment_methods'],
    dependencies=[Depends(get_current_user)],
)


def get_method_or_404(
    session: SessionDep, method_id: Annotated[int, Path(ge=1)]
) -> PaymentMethod:
    return payment_methods.get_method(session, method_id)


MethodDep = Annotated[PaymentMethod, Depends(get_method_or_404)]


@router.get('/', response_model=list[PaymentMethodPublic])
def list_methods(
    session: SessionDep, active_only: Annotated[bool, Query()] = False
) -> Sequence[PaymentMethod]:
    return payment_methods.list_methods(session, active_only=active_only)


@router.post(
    '/',
    response_model=PaymentMethodPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_method(
    session: SessionDep, owner: OwnerDep, method_in: PaymentMethodCreate
) -> PaymentMethod:
    return payment_methods.create_method(session, method_in, actor=owner)


@router.patch('/{method_id}', response_model=PaymentMethodPublic)
def update_method(
    session: SessionDep,
    owner: OwnerDep,
    method: MethodDep,
    method_in: PaymentMethodUpdate,
) -> PaymentMethod:
    return payment_methods.update_method(
        session, method, method_in, actor=owner
    )
