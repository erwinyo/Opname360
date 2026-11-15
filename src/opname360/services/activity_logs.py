from sqlmodel import Session, col, func, select

from opname360.models import (
    ActivityLog,
    ActivityLogEntry,
    ActivityLogFilter,
    ActivityLogPage,
    User,
)


def list_entries(
    session: Session, filters: ActivityLogFilter
) -> ActivityLogPage:
    query = select(ActivityLog, User.full_name).join(User, isouter=True)
    if filters.user_id is not None:
        query = query.where(ActivityLog.user_id == filters.user_id)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    rows = session.exec(
        query.order_by(col(ActivityLog.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return ActivityLogPage(
        items=[
            ActivityLogEntry.model_validate(entry, update={'user_name': name})
            for entry, name in rows
        ],
        total=total,
    )
