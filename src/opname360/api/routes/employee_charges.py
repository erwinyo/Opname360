from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from opname360.api.deps import OwnerDep, SessionDep, require_owner
from opname360.core.errors import NotFoundError
from opname360.models import (
    ChargeSettle,
    EmployeeCharge,
    EmployeeChargeFilter,
    EmployeeChargePage,
    EmployeeChargePublic,
    EmployeeChargeTotal,
)
from opname360.services import cash, documents, employee_charges


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


@router.post('/{charge_id}/settle')
def settle_charge(
    session: SessionDep,
    charge_id: Annotated[int, Path(ge=1)],
    data: ChargeSettle,
    owner: OwnerDep,
) -> EmployeeChargePublic:
    """Paid back in cash, or deducted from salary."""
    charge = session.get(EmployeeCharge, charge_id)
    if charge is None:
        raise NotFoundError('Ganti rugi tidak ditemukan.')
    charge = cash.settle_charge(
        session,
        charge,
        by_salary=data.by_salary,
        account_id=data.account_id,
        actor=owner,
    )
    return EmployeeChargePublic.model_validate(
        charge,
        update={
            'user_name': documents.user_name(session, charge.user_id) or '',
            'created_by_name': documents.user_name(session, charge.created_by),
        },
    )
