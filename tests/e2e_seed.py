"""Reset the test database for the browser tests in frontend/e2e.

Run by Playwright before it starts the server:
`uv run python -m tests.e2e_seed`.
"""

from sqlmodel import Session, create_engine

from .database import rebuild

from opname360.core.config import settings
from opname360.models import Role, UserCreate
from opname360.services import users


OWNER = UserCreate(
    username='demo',
    full_name='Demo Pemilik',
    role=Role.owner,
    password='demo-pemilik-1',
)


def main() -> None:
    assert settings.test_database_url, 'Set TEST_DATABASE_URL in .env'
    rebuild(settings.test_database_url)
    engine = create_engine(settings.test_database_url)
    with Session(engine) as session:
        users.create_user(session, OWNER, actor=None)
    engine.dispose()


if __name__ == '__main__':
    main()
