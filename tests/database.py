from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlmodel import create_engine


def rebuild(url: str) -> None:
    """Wipe the database at `url` and rebuild it from the migrations."""
    name = url.rsplit('/', 1)[-1]
    assert name.endswith('_test'), f'Refusing to wipe "{name}": not a test DB'

    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA public CASCADE'))
        connection.execute(text('CREATE SCHEMA public'))
    engine.dispose()

    config = Config('alembic.ini')
    config.set_main_option('sqlalchemy.url', url)
    command.upgrade(config, 'head')
