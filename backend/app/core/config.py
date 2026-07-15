"""Centralized configuration (Infrastructure layer).

Every environment-specific value is loaded here from environment variables / .env.
Nothing else in the codebase should read os.environ directly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to backend/.env so config loads regardless of the process CWD
# (the app can be launched from the repo root, backend/, or a preview harness).
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Application ----
    app_name: str = "ARGUS"
    app_description: str = "AI Cyber Decision Intelligence Platform"
    app_version: str = "1.0.0"
    environment: str = "development"          # development | production
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # ---- Database (MySQL by default; DATABASE_URL overrides the parts) ----
    database_url: str | None = None
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_db: str = "argus"

    # ---- Security / Auth (JWT) ----
    secret_key: str = "argus-dev-secret-change-me-please-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # ---- AI Decision Layer (OpenRouter). Offline grounded fallback always available. ----
    ai_enabled: bool = True
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct"
    ai_timeout_seconds: float = 30.0

    # ---- CORS (React dev server) — comma separated ----
    cors_origins_raw: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Misc ----
    log_level: str = "INFO"
    synthetic_seed: int = 42
    reports_dir: str = "reports_output"

    # ------------------------------------------------------------------ helpers
    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_url(self) -> str:
        """Full SQLAlchemy connection URL used by the application engine."""
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_server_url(self) -> str:
        """Server-level URL (no database) — used once to CREATE DATABASE."""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/?charset=utf8mb4"
        )

    @property
    def is_mysql(self) -> bool:
        return self.sqlalchemy_url.startswith("mysql")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
