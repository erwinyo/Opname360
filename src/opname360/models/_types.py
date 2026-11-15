from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum


def enum_type(enum: type[StrEnum]) -> Any:
    """Column type storing a StrEnum as text.

    A native PostgreSQL enum would need a hand-written migration for every
    new member; statuses and reasons gain members with each slice.
    """
    return Enum(
        enum,
        native_enum=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
