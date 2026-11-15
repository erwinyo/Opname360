from fastapi import APIRouter, Response, status

from opname360.api.deps import (
    SESSION_COOKIE,
    CurrentUserDep,
    SessionDep,
    SessionTokenDep,
)
from opname360.core.config import settings
from opname360.models import LoginRequest, User, UserPublic
from opname360.services import auth as auth_service


router = APIRouter(prefix='/auth', tags=['auth'])

# The server ends a session after 12 idle hours; the cookie only has to
# outlive that.
COOKIE_MAX_AGE = 7 * 24 * 60 * 60


@router.post('/login', response_model=UserPublic)
def login(
    session: SessionDep, credentials: LoginRequest, response: Response
) -> User:
    user = auth_service.authenticate(
        session, credentials.username, credentials.password
    )
    token = auth_service.start_session(session, user)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.environment == 'production',
        samesite='lax',
    )
    return user


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(
    session: SessionDep, response: Response, token: SessionTokenDep = None
) -> None:
    if token:
        auth_service.end_session(session, token)
    response.delete_cookie(SESSION_COOKIE)


@router.get('/me', response_model=UserPublic)
def read_me(user: CurrentUserDep) -> User:
    return user
