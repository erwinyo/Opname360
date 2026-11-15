from alembic import context
from sqlmodel import SQLModel, create_engine

from opname360 import models  # noqa: F401  (registers every table)
from opname360.core.config import settings


config = context.config
# Tests point this at the test database; otherwise use DATABASE_URL.
url = config.get_main_option('sqlalchemy.url') or settings.database_url
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
