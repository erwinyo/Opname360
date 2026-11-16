from typing import Annotated

from fastapi import APIRouter, Depends, Query

from opname360.api.deps import SessionDep, require_owner
from opname360.models import (
    EmployeeChargeFilter,
    EmployeeChargePage,
    EmployeeChargeTotal,
)
from opname360.services import employee_charges


router = APIRouter(
    prefix='/employee-charges',
    tags=['employee_charges'],
    dependencies=[Depends(require_owner)],
)


@router.get('/')
def list_charges(
    session: SessionDep, filters: Annotated[EmployeeChargeFilter, Query()]
) -> EmployeeChargePage:
    return employee_charges.list_charges(session, filters)


@router.get('/totals')
def outstanding_totals(session: SessionDep) -> list[EmployeeChargeTotal]:
    """What each employee still owes."""
    return employee_charges.outstanding_totals(session)
