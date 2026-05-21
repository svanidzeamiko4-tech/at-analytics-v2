"""
Structured logging (loguru) — Enterprise Phase 0.

Why: central error capture for workers, migration, and future admin/Telegram services.
Does not replace Streamlit UI; call `configure_logging()` from workers/scripts only until wired in app.
"""

from __future__ import annotations

import sys

from loguru import logger

from core.config import get_settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    logger.add(
        settings.log_dir / "at_{time:YYYY-MM-DD}.log",
        rotation="50 MB",
        retention="14 days",
        level=settings.log_level,
        encoding="utf-8",
    )
    _configured = True
