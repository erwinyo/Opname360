from sqlmodel import Session

from opname360.models import ActivityLog, User


def record(
    session: Session,
    *,
    actor: User | None,
    action: str,
    summary: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> None:
    """Add a log line to the caller's transaction; the caller commits."""
    session.add(
        ActivityLog(
            user_id=actor.id if actor else None,
            action=action,
            summary=summary,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )
