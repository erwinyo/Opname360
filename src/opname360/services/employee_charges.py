from sqlmodel import Session, col, func, select

from opname360.models import (
    ChargeStatus,
    EmployeeCharge,
    EmployeeChargeFilter,
    EmployeeChargePage,
    EmployeeChargePublic,
    EmployeeChargeTotal,
    User,
)
from opname360.models._types import utc_now
from opname360.services import documents


def list_charges(
    session: Session, filters: EmployeeChargeFilter
) -> EmployeeChargePage:
    query = select(EmployeeCharge, User.full_name).join(
        User, col(EmployeeCharge.user_id) == User.id
    )
    if filters.user_id is not None:
        query = query.where(EmployeeCharge.user_id == filters.user_id)
    if filters.status is not None:
        query = query.where(EmployeeCharge.status == filters.status)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    rows = session.exec(
        query.order_by(col(EmployeeCharge.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return EmployeeChargePage(
        items=[
            EmployeeChargePublic.model_validate(
                charge,
                update={
                    'user_name': name,
                    'created_by_name': documents.user_name(
                        session, charge.created_by
                    ),
                },
            )
            for charge, name in rows
        ],
        total=total,
    )


def outstanding_totals(session: Session) -> list[EmployeeChargeTotal]:
    """Per employee with anything outstanding, the most owed first."""
    amount = func.sum(EmployeeCharge.amount)
    rows = session.exec(
        select(User.id, User.full_name, amount, func.count())
        .join(EmployeeCharge, col(EmployeeCharge.user_id) == User.id)
        .where(EmployeeCharge.status == ChargeStatus.outstanding)
        .group_by(col(User.id), col(User.full_name))
        .order_by(amount.desc(), col(User.full_name))
    ).all()
    return [
        EmployeeChargeTotal(
            user_id=user_id,
            full_name=name,
            outstanding_amount=owed,
            outstanding_count=n,
        )
        for user_id, name, owed, n in rows
    ]


def cancel_outstanding(
    session: Session, *, source_type: str, source_id: int
) -> int:
    """Cancel what a reversed document charged and is not yet settled."""
    charges = session.exec(
        select(EmployeeCharge).where(
            EmployeeCharge.source_type == source_type,
            EmployeeCharge.source_id == source_id,
            EmployeeCharge.status == ChargeStatus.outstanding,
        )
    ).all()
    now = utc_now()
    for charge in charges:
        charge.status = ChargeStatus.cancelled
        charge.cancelled_at = now
        session.add(charge)
    return len(charges)
