"""Application configuration."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"


def normalize_database_url(url: str) -> str:
    """Render/Heroku often provide postgres://; SQLAlchemy needs postgresql://."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Stock Market Analytics Platform"
    app_version: str = "1.0.0"
    debug: bool = True
    secret_key: str = "change-me-in-production-use-a-long-random-secret-key-32chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'stock_analytics.db'}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    rate_limit_per_minute: int = 120
    default_admin_email: str = "admin@signalforge.app"
    default_admin_password: str = "Admin@12345"
    scheduler_enabled: bool = True
    data_lookback_years: int = 5

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        return normalize_database_url(str(value))

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
