from typing import Annotated

from fastapi import APIRouter, Depends, Query

from opname360.api.deps import SessionDep, require_owner
from opname360.models import ActivityLogFilter, ActivityLogPage
from opname360.services import activity_logs


router = APIRouter(
    prefix='/activity-log',
    tags=['activity_log'],
    dependencies=[Depends(require_owner)],
)


@router.get('/')
def list_entries(
    session: SessionDep, filters: Annotated[ActivityLogFilter, Query()]
) -> ActivityLogPage:
    return activity_logs.list_entries(session, filters)
