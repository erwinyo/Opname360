from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from opname360.api.deps import OwnerDep, SessionDep, require_owner
from opname360.models import (
    PasswordReset,
    User,
    UserCreate,
    UserPublic,
    UserUpdate,
)
from opname360.services import users as users_service


router = APIRouter(
    prefix='/users', tags=['users'], dependencies=[Depends(require_owner)]
)


def get_user_or_404(
    session: SessionDep, user_id: Annotated[int, Path(ge=1)]
) -> User:
    return users_service.get_user(session, user_id)


UserDep = Annotated[User, Depends(get_user_or_404)]


@router.get('/', response_model=list[UserPublic])
def list_users(session: SessionDep) -> Sequence[User]:
    return users_service.list_users(session)


@router.post(
    '/', response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
def create_user(
    session: SessionDep, owner: OwnerDep, user_in: UserCreate
) -> User:
    return users_service.create_user(session, user_in, actor=owner)


@router.patch('/{user_id}', response_model=UserPublic)
def update_user(
    session: SessionDep, owner: OwnerDep, user: UserDep, user_in: UserUpdate
) -> User:
    return users_service.update_user(session, user, user_in, actor=owner)


@router.post('/{user_id}/password', status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    session: SessionDep, owner: OwnerDep, user: UserDep, body: PasswordReset
) -> None:
    users_service.reset_password(session, user, body.password, actor=owner)
