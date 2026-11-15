from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col

from opname360.core.config import settings
from opname360.models import DocumentCounter
from opname360.models._types import utc_now


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
