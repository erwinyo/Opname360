"""What every stock document shares: numbers, locking and Reversals."""

from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import SQLModel, Session, col, select

from opname360.core.config import settings
from opname360.core.errors import ConflictError
from opname360.models import (
    DocumentCounter,
    DocumentStatus,
    Reversal,
    ReversalPublic,
    User,
)
from opname360.models._types import utc_now
from opname360.services import activity_log, costing


REVERSAL_PREFIX = 'BTL'  # Batal


class Reversible(Protocol):
    """A stock document: anything with an id and a status."""

    id: int | None
    status: DocumentStatus


def shop_now() -> datetime:
    return utc_now().astimezone(ZoneInfo(settings.timezone))


def next_number(session: Session, prefix: str) -> str:
    """The next document number for `prefix` this month: BM-2611-0001.

    Safe when two documents are completed at once: the counter row is locked
    until the caller commits.
    """
    period = shop_now().strftime('%y%m')
    number = session.exec(
        insert(DocumentCounter)
        .values(prefix=prefix, period=period, last_number=1)
        .on_conflict_do_update(
            index_elements=['prefix', 'period'],
            set_={'last_number': DocumentCounter.last_number + 1},
        )
        .returning(col(DocumentCounter.last_number))
    ).scalar_one()
    return f'{prefix}-{period}-{number:04d}'


def lock[Document: SQLModel](
    session: Session, model: type[Document], document_id: int
) -> Document:
    """Re-read a document and hold it until commit, so two people can't act
    on it at once."""
    document = session.get(
        model, document_id, with_for_update=True, populate_existing=True
    )
    assert document is not None
    return document


def user_name(session: Session, user_id: int | None) -> str | None:
    user = session.get(User, user_id) if user_id else None
    return user.full_name if user else None


def reversal_public(
    session: Session, document_type: str, document_id: int | None
) -> ReversalPublic | None:
    reversal = session.exec(
        select(Reversal).where(
            Reversal.document_type == document_type,
            Reversal.document_id == document_id,
        )
    ).first()
    if reversal is None:
        return None
    return ReversalPublic.model_validate(
        reversal,
        update={'created_by_name': user_name(session, reversal.created_by)},
    )


def reverse(
    session: Session,
    document: Reversible,
    *,
    document_type: str,
    label: str,
    reason: str,
    actor: User,
) -> Reversal:
    """Undo a completed document's stock and mark it reversed.

    `label` names the document in messages: "barang masuk BM-2611-0001".
    The caller has locked `document` and commits.
    """
    status = document.status
    document_id = document.id
    assert document_id is not None
    if status == DocumentStatus.reversed:
        raise ConflictError(f'{label.capitalize()} sudah dibatalkan.')
    if status != DocumentStatus.completed:
        raise ConflictError(
            f'{label.capitalize()} belum selesai, jadi tidak perlu dibatalkan.'
        )
    reason = reason.strip()
    if not reason:
        raise ConflictError('Alasan pembatalan wajib diisi.')

    reversal = Reversal(
        number=next_number(session, REVERSAL_PREFIX),
        document_type=document_type,
        document_id=document_id,
        reason=reason,
        created_by=actor.id,
    )
    session.add(reversal)
    costing.reverse(
        session,
        document_type=document_type,
        document_id=document_id,
        number=reversal.number,
        actor=actor,
    )
    document.status = DocumentStatus.reversed
    session.add(document)
    activity_log.record(
        session,
        actor=actor,
        action=f'{document_type}.reverse',
        summary=f'Membatalkan {label} ({reversal.number}): {reason}',
        entity_type=document_type,
        entity_id=document_id,
    )
    return reversal
