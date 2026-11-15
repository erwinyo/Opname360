from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from the environment, then from `.env` (see `.env.example`)."""

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    project_name: str = 'Opname360'
    environment: Literal['local', 'production'] = 'local'
    database_url: str
    test_database_url: str | None = None
    frontend_dist: Path = Path('frontend/dist')


settings = Settings()
