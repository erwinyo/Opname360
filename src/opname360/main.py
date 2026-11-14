from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from opname360.api.main import api_router
from opname360.core.config import settings
from opname360.core.db import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    create_db_and_tables()
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)
app.include_router(api_router)
