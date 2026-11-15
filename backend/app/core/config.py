from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(ROOT_DIR / ".env"),
            str(ROOT_DIR / ".env.local"),
            str(BACKEND_DIR / ".env"),
            str(BACKEND_DIR / ".env.local"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    PROJECT_NAME: str = "Human-AI Interaction Lab"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg://app_user:change_me@localhost:5432/hai_lab"
    DATABASE_URL_UNPOOLED: str | None = None
    SECRET_KEY: str = "dev_secret_key_replace_in_production_987654321"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    @field_validator("DATABASE_URL", "DATABASE_URL_UNPOOLED", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, v: str | None) -> str | None:
        if not v:
            return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v


settings = Settings()
