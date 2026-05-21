"""
SQLAlchemy engine with connection pooling (Enterprise Phase 1).

Why: SQLite cannot serve ~200 concurrent Streamlit sessions; Postgres + pool does.
Not used by the live app until USE_POSTGRES=true and data_loader adapter (Phase 1b).
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from core.config import get_settings

_engine: Engine | None = None


@lru_cache
def _pool_kwargs() -> dict:
    return {
        "pool_size": 20,
        "max_overflow": 30,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }


def get_engine() -> Engine:
    """Return singleton engine (call only when USE_POSTGRES=true)."""
    global _engine
    settings = get_settings()
    if not settings.use_postgres:
        raise RuntimeError(
            "PostgreSQL is disabled (USE_POSTGRES=false). "
            "App continues to use SQLite via data_loader."
        )
    if _engine is None:
        _engine = create_engine(settings.database_url, **_pool_kwargs())
    return _engine


def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
