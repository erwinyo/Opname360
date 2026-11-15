from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from opname360.api.main import api_router
from opname360.core.config import settings
from opname360.core.errors import AppError


def operation_id(route: APIRoute) -> str:
    """Short ids (`users-create_user`) give the generated client clean names."""
    tag = route.tags[0] if route.tags else 'api'
    return f'{tag}-{route.name}'


app = FastAPI(
    title=settings.project_name, generate_unique_id_function=operation_id
)
app.include_router(api_router)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content={'detail': exc.detail}
    )


# Locally the API also runs without a frontend build (tests, API-only work).
# In production a missing build stops the app from starting.
if settings.environment == 'production' or settings.frontend_dist.is_dir():
    app.frontend('/', directory=settings.frontend_dist)
