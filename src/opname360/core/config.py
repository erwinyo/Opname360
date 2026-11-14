from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_name: str = "Opname360"
    database_url: str = "sqlite:///./opname360.db"


settings = Settings()
