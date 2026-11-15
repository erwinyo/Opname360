from fastapi import APIRouter, Depends, HTTPException, status

from opname360.api.deps import verify_same_origin
from opname360.api.routes import auth, health, users


api_router = APIRouter(
    prefix='/api/v1', dependencies=[Depends(verify_same_origin)]
)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)


# Last on purpose: without it an unknown API path would fall through to the
# frontend and answer with index.html.
@api_router.get('/{path:path}', include_in_schema=False)
def api_not_found(path: str) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
