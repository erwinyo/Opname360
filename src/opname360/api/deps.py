from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlmodel import Session

from opname360.core.db import get_session
from opname360.models import Role, User
from opname360.services import auth as auth_service


SESSION_COOKIE = 'opname360_session'
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}

SessionDep = Annotated[Session, Depends(get_session)]
SessionTokenDep = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def verify_same_origin(request: Request) -> None:
    """Refuse a browser request that changes something from another site."""
    origin = request.headers.get('origin')
    if request.method in SAFE_METHODS or origin is None:
        return
    if urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Permintaan dari situs lain ditolak.',
        )


def get_current_user(
    session: SessionDep, token: SessionTokenDep = None
) -> User:
    user = auth_service.get_session_user(session, token) if token else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Silakan masuk terlebih dahulu.',
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_owner(user: CurrentUserDep) -> User:
    if user.role != Role.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Hanya Pemilik yang boleh melakukan ini.',
        )
    return user


OwnerDep = Annotated[User, Depends(require_owner)]
