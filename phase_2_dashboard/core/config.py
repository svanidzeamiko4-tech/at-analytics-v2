"""
Central configuration from environment variables.

Active deployment (current phase): USE_POSTGRES=false → SQLite only
  (amiko_v3.db + phase_2_dashboard/auth/at_auth.db). See docs/LOCAL_SQLITE_ARCHITECTURE.md.

PostgreSQL paths exist for a future phase; leave USE_POSTGRES=false unless re-approved.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PKG = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _PKG.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Phase 1: when false, all existing code keeps using SQLite (unchanged behavior)
    use_postgres: bool = Field(False, alias="USE_POSTGRES")

    database_url: str = Field(
        "postgresql+psycopg://at_user:password@localhost:5432/at_analytics",
        alias="DATABASE_URL",
    )

    analytics_db_path: Path = Field(
        default_factory=lambda: _PROJECT_ROOT / "amiko_v3.db",
        alias="AT_ANALYTICS_DB",
    )
    auth_db_path: Path = Field(
        default_factory=lambda: _PKG / "auth" / "at_auth.db",
        alias="AT_AUTH_DB",
    )

    auth_secret: str = Field("at-analytics-dev-secret-change-me", alias="AT_AUTH_SECRET")

    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        "claude-3-5-haiku-20241022",
        alias="ANTHROPIC_MODEL",
    )

    rs_ge_use_mock: bool = Field(True, alias="RS_GE_USE_MOCK")
    rs_ge_username: str = Field("", alias="RS_GE_USERNAME")
    rs_ge_password: str = Field("", alias="RS_GE_PASSWORD")
    rs_ge_soap_url: str = Field("", alias="RS_GE_SOAP_URL")
    rs_ge_company_code: str = Field("", alias="RS_GE_COMPANY_CODE")
    rs_sync_interval_minutes: int = Field(30, alias="RS_SYNC_INTERVAL_MINUTES")

    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "logs", alias="LOG_DIR")

    at_env: str = Field("development", alias="AT_ENV")
    at_debug: bool = Field(False, alias="AT_DEBUG")

    # Reserved for Phase 4+ (admin panel, Telegram bot) — no behavior yet
    telegram_bot_token: str | None = Field(None, alias="TELEGRAM_BOT_TOKEN")
    admin_api_enabled: bool = Field(False, alias="ADMIN_API_ENABLED")

    @property
    def is_production(self) -> bool:
        return self.at_env.strip().lower() == "production"

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    def resolved_analytics_sqlite(self) -> Path:
        p = self.analytics_db_path
        return p if p.is_absolute() else _PROJECT_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
